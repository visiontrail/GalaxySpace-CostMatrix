"""主、备模型端点选择与轻量熔断状态。

CostMatrix 当前以单个 Uvicorn worker 运行，因此状态保存在进程内即可覆盖全部
请求。路由原则与 RavenAIService 一致：健康时永远先用主端点；只有首个模型
输出前的失败才记为可接管故障；达到阈值后在冷却期优先使用备用端点，冷却
结束再让真实请求探测主端点。路由状态绝不能阻断 Agent 本身。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.ai_settings_service import EffectiveAISettings, ModelEndpointSettings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SLOT_PRIMARY = "primary"
SLOT_BACKUP = "backup"


@dataclass(frozen=True)
class EndpointChoice:
    slot: str
    provider: str
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_settings(cls, endpoint: ModelEndpointSettings) -> "EndpointChoice":
        return cls(
            slot=endpoint.slot,
            provider=endpoint.provider,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
            model=endpoint.model,
        )


class _RouterState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fingerprint = ""
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._last_error = ""

    def _sync(self, fingerprint: str) -> None:
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        self._failures = 0
        self._opened_at = None
        self._last_error = ""

    def snapshot(self, fingerprint: str, cooldown: int) -> Dict[str, Any]:
        with self._lock:
            self._sync(fingerprint)
            now = time.monotonic()
            open_ = self._opened_at is not None and now < self._opened_at + cooldown
            remaining = (
                max(0, int(self._opened_at + cooldown - now))
                if open_ and self._opened_at is not None
                else 0
            )
            return {
                "primary_breaker_open": open_,
                "consecutive_failures": self._failures,
                "cooldown_remaining_seconds": remaining,
                "last_error": self._last_error,
            }

    def success(self, fingerprint: str) -> None:
        with self._lock:
            self._sync(fingerprint)
            recovered = self._opened_at is not None or self._failures > 0
            self._failures = 0
            self._opened_at = None
            self._last_error = ""
        if recovered:
            logger.warning("model_router: 主模型已恢复，后续请求重新优先使用主模型")

    def failure(self, fingerprint: str, *, threshold: int, error: str) -> bool:
        with self._lock:
            self._sync(fingerprint)
            self._failures += 1
            self._last_error = error[:500]
            opened = self._failures >= max(1, threshold)
            if opened:
                self._opened_at = time.monotonic()
            count = self._failures
        if opened:
            logger.warning(
                "model_router: 主模型连续失败 %s 次，冷却期内优先使用备用模型: %s",
                count,
                error,
            )
        return opened

    def reset(self) -> None:
        with self._lock:
            self._fingerprint = ""
            self._failures = 0
            self._opened_at = None
            self._last_error = ""


_state = _RouterState()


def _primary(effective: EffectiveAISettings) -> EndpointChoice:
    return EndpointChoice(
        slot=SLOT_PRIMARY,
        provider=effective.provider,
        api_key=effective.api_key,
        base_url=effective.base_url,
        model=effective.model,
    )


def _fingerprint(effective: EffectiveAISettings) -> str:
    return "|".join(
        (effective.provider, effective.base_url, effective.model, str(effective.router_enabled))
    )


def candidates(effective: EffectiveAISettings) -> List[EndpointChoice]:
    """返回本轮应该尝试的端点，按优先级排序。"""
    primary = _primary(effective)
    backup = (
        EndpointChoice.from_settings(effective.backup)
        if effective.backup_enabled and effective.backup and effective.backup.configured
        else None
    )
    if not effective.router_enabled or backup is None:
        return [primary]

    snapshot = _state.snapshot(
        _fingerprint(effective), effective.router_cooldown_seconds
    )
    if snapshot["primary_breaker_open"]:
        return [backup, primary]
    return [primary, backup]


def record_success(effective: EffectiveAISettings, slot: str) -> None:
    if slot == SLOT_PRIMARY:
        _state.success(_fingerprint(effective))


def record_failure(effective: EffectiveAISettings, slot: str, error: BaseException) -> None:
    if slot != SLOT_PRIMARY or not effective.router_enabled:
        return
    _state.failure(
        _fingerprint(effective),
        threshold=effective.router_failure_threshold,
        error=f"{type(error).__name__}: {error}",
    )


def health_snapshot(effective: EffectiveAISettings) -> Dict[str, Any]:
    snapshot = _state.snapshot(
        _fingerprint(effective), effective.router_cooldown_seconds
    )
    backup_configured = bool(
        effective.backup_enabled and effective.backup and effective.backup.configured
    )
    open_ = bool(snapshot["primary_breaker_open"] and backup_configured)
    return {
        "enabled": effective.router_enabled,
        "serving_slot": SLOT_BACKUP if open_ else SLOT_PRIMARY,
        "primary_breaker_open": open_,
        "consecutive_failures": snapshot["consecutive_failures"],
        "cooldown_remaining_seconds": snapshot["cooldown_remaining_seconds"],
        "last_error": snapshot["last_error"],
        "primary": {
            "configured": bool(effective.api_key and effective.base_url and effective.model),
            "provider": effective.provider,
            "model": effective.model,
        },
        "backup": {
            "configured": backup_configured,
            "provider": effective.backup.provider if effective.backup else None,
            "model": effective.backup.model if effective.backup else None,
        },
    }


def reset_for_tests() -> None:
    _state.reset()
