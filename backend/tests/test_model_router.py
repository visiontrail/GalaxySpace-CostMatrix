"""主备模型路由的端点顺序、故障接管和提交边界测试。"""
import asyncio

import pytest

from app.agents.routed_query import EndpointSwitchNotice, routed_query
from app.services import model_router
from app.services.ai_settings_service import EffectiveAISettings, ModelEndpointSettings


def effective(**overrides):
    values = {
        "provider": "yhroot",
        "api_key": "primary-key",
        "base_url": "https://oneapi.yhroot.com",
        "model": "yinhe-thinking",
        "max_turns": 4,
        "request_timeout_seconds": 30,
        "total_timeout_seconds": 60,
        "max_result_rows": 100,
        "system_prompt": "test",
        "backup": ModelEndpointSettings(
            slot="backup",
            provider="kimi",
            api_key="backup-key",
            base_url="https://api.moonshot.cn/anthropic",
            model="kimi-k3",
        ),
        "backup_enabled": True,
        "router_enabled": True,
        "router_first_token_timeout_seconds": 1,
        "router_failure_threshold": 1,
        "router_cooldown_seconds": 60,
    }
    values.update(overrides)
    return EffectiveAISettings(**values)


@pytest.fixture(autouse=True)
def reset_router():
    model_router.reset_for_tests()
    yield
    model_router.reset_for_tests()


def test_primary_is_first_while_healthy_and_backup_after_trip():
    settings = effective()
    assert [item.slot for item in model_router.candidates(settings)] == [
        "primary",
        "backup",
    ]

    model_router.record_failure(settings, "primary", OSError("gateway unavailable"))

    assert [item.slot for item in model_router.candidates(settings)] == [
        "backup",
        "primary",
    ]
    snapshot = model_router.health_snapshot(settings)
    assert snapshot["primary_breaker_open"] is True
    assert snapshot["serving_slot"] == "backup"


@pytest.mark.asyncio
async def test_pre_output_failure_switches_to_backup():
    settings = effective()
    attempted = []

    class SystemFrame:
        subtype = "init"
        data = {}

    class ModelFrame:
        pass

    async def fake_query(*, prompt, options):
        attempted.append(options.slot)
        if options.slot == "primary":
            yield SystemFrame()
            raise OSError("primary is down")
        yield ModelFrame()

    messages = []
    async for message in routed_query(
        prompt="hello",
        effective=settings,
        make_options=lambda choice: choice,
        sdk_query=fake_query,
    ):
        messages.append(message)

    assert attempted == ["primary", "backup"]
    assert any(isinstance(item, EndpointSwitchNotice) for item in messages)
    assert isinstance(messages[-1], ModelFrame)


@pytest.mark.asyncio
async def test_committed_run_is_never_replayed_on_backup():
    settings = effective()
    attempted = []

    class ModelFrame:
        pass

    async def fake_query(*, prompt, options):
        attempted.append(options.slot)
        yield ModelFrame()
        raise RuntimeError("failed after model output")

    with pytest.raises(RuntimeError, match="after model output"):
        async for _ in routed_query(
            prompt="hello",
            effective=settings,
            make_options=lambda choice: choice,
            sdk_query=fake_query,
        ):
            pass

    assert attempted == ["primary"]


@pytest.mark.asyncio
async def test_first_output_timeout_switches_to_backup():
    settings = effective(router_first_token_timeout_seconds=0.01)
    attempted = []

    class ModelFrame:
        pass

    async def fake_query(*, prompt, options):
        attempted.append(options.slot)
        if options.slot == "primary":
            await asyncio.sleep(1)
        yield ModelFrame()

    messages = []
    async for message in routed_query(
        prompt="hello",
        effective=settings,
        make_options=lambda choice: choice,
        sdk_query=fake_query,
    ):
        messages.append(message)

    assert attempted == ["primary", "backup"]
    assert any(isinstance(item, EndpointSwitchNotice) for item in messages)
