"""CostMatrixAgent 超时语义的回归测试。

一次提问会展开成多轮模型调用和多次数据库查询，正常也可能持续数分钟。
超时必须按「静默多久」判定，而不是按整轮总耗时判定。
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock  # noqa: E402

from app.agents.cost_agent import CostMatrixAgent  # noqa: E402
from app.services.ai_settings_service import EffectiveAISettings  # noqa: E402


def _settings(*, stall: float, total: float) -> EffectiveAISettings:
    return EffectiveAISettings(
        provider="anthropic",
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        max_turns=12,
        request_timeout_seconds=stall,
        total_timeout_seconds=total,
        max_result_rows=10,
        system_prompt="test",
    )


def _fake_query(delays, *, final):
    """delays 是每条消息之前的等待秒数，用来模拟模型的推进节奏。"""

    async def query(*, prompt, options):  # noqa: ARG001
        for delay in delays:
            await asyncio.sleep(delay)
            yield AssistantMessage(content=[TextBlock(text="步骤")], model="test-model")
        if final is not None:
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=len(delays),
                session_id="test-session",
                result=final,
            )

    return query


def _run(settings):
    async def collect():
        return [
            event
            async for event in CostMatrixAgent().run_stream(
                user_message="各部门差旅成本如何？",
                history=[],
                runtime_settings=settings,
            )
        ]

    return asyncio.run(collect())


def test_long_run_survives_while_agent_keeps_making_progress(monkeypatch):
    # 总耗时约 0.75s，远超 0.3s 的静默阈值，但每 0.15s 就有一条新消息。
    monkeypatch.setattr("claude_agent_sdk.query", _fake_query([0.15] * 5, final="分析完成"))

    final = _run(_settings(stall=0.3, total=30))[-1]

    assert final["event"] == "final"
    assert final["answer"] == "分析完成"
    assert final["interrupted"] is False


def test_stalled_run_without_any_output_raises(monkeypatch):
    monkeypatch.setattr("claude_agent_sdk.query", _fake_query([5.0], final="不会到达"))

    with pytest.raises(RuntimeError, match="没有响应"):
        _run(_settings(stall=0.2, total=30))


def test_total_cap_keeps_partial_answer_and_marks_it_interrupted(monkeypatch):
    monkeypatch.setattr("claude_agent_sdk.query", _fake_query([0.05] * 40, final="不会到达"))

    final = _run(_settings(stall=0.5, total=0.5))[-1]

    assert final["event"] == "final"
    assert final["interrupted"] is True
    assert "总时长上限" in final["answer"]
    # 已经拿到的正文必须保留，不能被超时提示顶掉。
    assert final["answer"].startswith("步骤")


def test_total_cap_is_never_shorter_than_the_stall_window(monkeypatch):
    monkeypatch.setattr("claude_agent_sdk.query", _fake_query([0.15] * 4, final="分析完成"))

    # total 配得比 stall 还小时应被抬到 stall，不能切断正常推进的会话。
    assert _run(_settings(stall=2, total=0.1))[-1]["answer"] == "分析完成"
