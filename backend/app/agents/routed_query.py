"""在首个模型输出前安全地把 Claude Agent SDK 请求切换到备用端点。"""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, AsyncIterator, Callable, List, Optional, Tuple

from app.services import model_router
from app.services.ai_settings_service import EffectiveAISettings
from app.services.model_router import EndpointChoice
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AllEndpointsUnavailable(RuntimeError):
    def __init__(self, failures: List[Tuple[str, BaseException]]) -> None:
        self.failures = failures
        detail = "; ".join(
            f"{slot}: {type(error).__name__}: {error}" for slot, error in failures
        ) or "没有可用端点"
        super().__init__(f"主模型与备用模型均不可用（{detail}）")


class EndpointAttemptError(RuntimeError):
    pass


class EndpointSwitchNotice:
    """与 SDK SystemMessage 相似的内部通知，不会被当作模型输出。"""

    subtype = "endpoint_switch"
    content = None
    event = None

    def __init__(
        self,
        *,
        from_endpoint: EndpointChoice,
        to_endpoint: EndpointChoice,
        reason: str,
        waited_ms: int,
    ) -> None:
        self.data = {
            "from_slot": from_endpoint.slot,
            "from_provider": from_endpoint.provider,
            "to_slot": to_endpoint.slot,
            "to_provider": to_endpoint.provider,
            "to_model": to_endpoint.model,
            "reason": reason,
            "waited_ms": waited_ms,
            "message": (
                f"{from_endpoint.provider} 主模型不可用，已自动切换到 "
                f"{to_endpoint.provider} 备用模型 {to_endpoint.model}"
            ),
        }


def _is_pre_model_frame(message: Any) -> bool:
    return (
        isinstance(getattr(message, "subtype", None), str)
        and isinstance(getattr(message, "data", None), dict)
    )


def _is_init_frame(message: Any) -> bool:
    return getattr(message, "subtype", None) == "init" and _is_pre_model_frame(message)


def _result_error(message: Any) -> Optional[EndpointAttemptError]:
    if not bool(getattr(message, "is_error", False)):
        return None
    errors = getattr(message, "errors", None) or []
    result = str(getattr(message, "result", None) or "")
    detail = "; ".join(str(item) for item in errors if item) or result
    return EndpointAttemptError(detail or "模型端点在首个输出前返回错误")


async def routed_query(
    *,
    prompt: str,
    effective: EffectiveAISettings,
    make_options: Callable[[EndpointChoice], Any],
    sdk_query: Callable[..., AsyncIterator[Any]],
    on_endpoint: Optional[Callable[[EndpointChoice], None]] = None,
) -> AsyncIterator[Any]:
    """尝试主端点，并仅在尚未提交任何模型输出时故障接管。"""
    choices = model_router.candidates(effective)
    failures: List[Tuple[str, BaseException]] = []
    first_token_timeout = float(effective.router_first_token_timeout_seconds)

    for index, choice in enumerate(choices):
        if on_endpoint is not None:
            on_endpoint(choice)
        stream = sdk_query(prompt=prompt, options=make_options(choice))
        iterator = stream.__aiter__()
        committed = False
        started = time.monotonic()
        deadline: Optional[float] = None
        if index < len(choices) - 1 and first_token_timeout > 0:
            deadline = asyncio.get_running_loop().time() + first_token_timeout

        try:
            while True:
                timeout: Optional[float] = None
                if not committed and deadline is not None:
                    timeout = deadline - asyncio.get_running_loop().time()
                    if timeout <= 0:
                        raise TimeoutError(
                            f"{choice.provider} 首个模型输出超过 {first_token_timeout:g} 秒"
                        )
                try:
                    if timeout is None:
                        message = await iterator.__anext__()
                    else:
                        message = await asyncio.wait_for(iterator.__anext__(), timeout)
                except StopAsyncIteration:
                    if not committed:
                        model_router.record_success(effective, choice.slot)
                    return
                except asyncio.TimeoutError as exc:
                    raise TimeoutError(
                        f"{choice.provider} 首个模型输出超过 {first_token_timeout:g} 秒"
                    ) from exc

                if not committed and _is_init_frame(message):
                    if deadline is not None:
                        deadline = asyncio.get_running_loop().time() + first_token_timeout
                    yield message
                    continue
                if not committed and _is_pre_model_frame(message):
                    yield message
                    continue
                if not committed:
                    result_error = _result_error(message)
                    if result_error is not None:
                        raise result_error
                    committed = True
                    model_router.record_success(effective, choice.slot)
                    logger.info(
                        "routed_query: committed slot=%s provider=%s model=%s ttft_ms=%s",
                        choice.slot,
                        choice.provider,
                        choice.model,
                        int((time.monotonic() - started) * 1000),
                    )
                yield message
            return
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001
            if committed:
                raise
            model_router.record_failure(effective, choice.slot, exc)
            failures.append((choice.slot, exc))
            remaining = len(choices) - index - 1
            logger.warning(
                "routed_query: endpoint failed before first model output "
                "slot=%s provider=%s model=%s: %s",
                choice.slot,
                choice.provider,
                choice.model,
                exc,
            )
            if remaining:
                next_choice = choices[index + 1]
                yield EndpointSwitchNotice(
                    from_endpoint=choice,
                    to_endpoint=next_choice,
                    reason=type(exc).__name__,
                    waited_ms=int((time.monotonic() - started) * 1000),
                )
                continue
        finally:
            aclose = getattr(stream, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

    raise AllEndpointsUnavailable(failures)
