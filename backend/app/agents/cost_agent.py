"""Claude Agent SDK 驱动的 CostMatrix 单智能体。"""
from __future__ import annotations

import asyncio
import contextlib
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

from app.agents.chart_tools import build_chart_mcp_server
from app.agents.database_tools import build_database_mcp_server
from app.services.ai_settings_service import EffectiveAISettings


class AgentConfigurationError(RuntimeError):
    """Agent 缺少可运行配置。"""


_DISABLED_BUILTIN_TOOLS = [
    "Bash",
    "BashOutput",
    "KillBash",
    "Edit",
    "MultiEdit",
    "Write",
    "Read",
    "NotebookEdit",
    "NotebookRead",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "WebSearch",
    "Task",
    "TaskOutput",
    "TaskStop",
    "TodoWrite",
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
]


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return ""
    lines = ["以下是本对话此前的消息，仅作为上下文："]
    for item in history[-12:]:
        role = "用户" if item.get("role") == "user" else "Agent"
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"[{role}] {content[:8_000]}")
    return "\n\n".join(lines)


def _extract_stream_delta(message: Any) -> str:
    event = getattr(message, "event", None)
    if not isinstance(event, dict) or event.get("type") != "content_block_delta":
        return ""
    delta = event.get("delta")
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    return str(delta.get("text") or "")


class CostMatrixAgent:
    """一个无需用户选择、固定面向成本分析的 Agent。"""

    async def run_stream(
        self,
        *,
        user_message: str,
        history: List[Dict[str, str]],
        runtime_settings: EffectiveAISettings,
    ) -> AsyncIterator[Dict[str, Any]]:
        if not runtime_settings.api_key:
            raise AgentConfigurationError(
                "尚未配置模型 API Key，请管理员先进入「设置」完成 Claude Agent 配置。"
            )
        if not runtime_settings.model:
            raise AgentConfigurationError("尚未配置模型名称")
        if not runtime_settings.base_url:
            raise AgentConfigurationError("尚未配置模型 Base URL")

        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ResultMessage,
                StreamEvent,
                TextBlock,
                ToolUseBlock,
                query,
            )
        except ImportError as exc:
            raise AgentConfigurationError(
                "Claude Agent SDK 未安装，请安装后端依赖后重试。"
            ) from exc

        charts: List[Dict[str, Any]] = []
        tool_trace: List[Dict[str, Any]] = []
        db_server, db_tools = build_database_mcp_server(
            max_rows=runtime_settings.max_result_rows,
            trace=tool_trace,
        )
        chart_server, chart_tool = build_chart_mcp_server(charts)
        all_tools = db_tools + [chart_tool]

        env = {
            "ANTHROPIC_API_KEY": runtime_settings.api_key,
            "ANTHROPIC_AUTH_TOKEN": runtime_settings.api_key,
            "ANTHROPIC_BASE_URL": runtime_settings.base_url,
            "ANTHROPIC_MODEL": runtime_settings.model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": runtime_settings.model,
            "API_TIMEOUT_MS": str(runtime_settings.request_timeout_seconds * 1_000),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        history_block = _format_history(history)
        prompt = (
            f"{history_block}\n\n当前用户问题：\n{user_message}"
            if history_block
            else user_message
        )

        partial_text = ""
        assistant_text = ""
        result_text = ""
        timeout_notice = ""
        emitted_chart_count = 0
        model = runtime_settings.model
        usage: Dict[str, Any] = {}

        with tempfile.TemporaryDirectory(prefix="costmatrix-agent-") as temp_dir:
            options = ClaudeAgentOptions(
                tools=[],
                allowed_tools=all_tools,
                disallowed_tools=_DISABLED_BUILTIN_TOOLS,
                system_prompt=runtime_settings.system_prompt,
                mcp_servers={
                    "costmatrix_db": db_server,
                    "costmatrix_chart": chart_server,
                },
                permission_mode="bypassPermissions",
                max_turns=runtime_settings.max_turns,
                model=runtime_settings.model,
                cwd=str(Path(temp_dir)),
                env=env,
                include_partial_messages=True,
            )

            yield {"event": "status", "phase": "thinking", "message": "正在理解问题并规划查询"}

            # 一次提问会触发多轮模型调用和多次工具查询，正常也可能持续数分钟。
            # 因此按「静默超时」计时：只要 SDK 还在推送消息就说明仍在推进，
            # request_timeout_seconds 只用于判定模型端卡死；总时长另有上限兜底。
            stall_seconds = runtime_settings.request_timeout_seconds
            total_seconds = max(
                runtime_settings.total_timeout_seconds,
                stall_seconds,
            )
            loop = asyncio.get_running_loop()
            total_deadline = loop.time() + total_seconds

            def next_deadline() -> float:
                return min(loop.time() + stall_seconds, total_deadline)

            stream = query(prompt=prompt, options=options)
            try:
                async with asyncio.timeout_at(next_deadline()) as guard:
                    async for message in stream:
                        guard.reschedule(next_deadline())

                        if isinstance(message, StreamEvent):
                            delta = _extract_stream_delta(message)
                            if delta:
                                partial_text += delta
                                yield {"event": "answer_delta", "delta": delta}

                        if isinstance(message, AssistantMessage):
                            model = message.model or model
                            if isinstance(message.usage, dict):
                                usage = message.usage
                            for block in message.content:
                                if isinstance(block, ToolUseBlock):
                                    yield {
                                        "event": "tool_use",
                                        "tool": block.name.split("__")[-1],
                                        "arguments": block.input,
                                    }
                                elif isinstance(block, TextBlock) and block.text:
                                    assistant_text += block.text

                        while emitted_chart_count < len(charts):
                            yield {
                                "event": "chart",
                                "chart": charts[emitted_chart_count],
                            }
                            emitted_chart_count += 1

                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                details = "; ".join(message.errors or [])
                                raise RuntimeError(
                                    details or message.result or "模型未能完成本轮请求"
                                )
                            result_text = str(message.result or "")
                            if isinstance(message.usage, dict):
                                usage = message.usage
            except TimeoutError as exc:
                if loop.time() >= total_deadline:
                    timeout_notice = f"本轮分析已达到总时长上限 {total_seconds} 秒，被中断。"
                else:
                    timeout_notice = f"模型连续 {stall_seconds} 秒没有响应，本轮分析被中断。"
                if not (partial_text or assistant_text or charts):
                    raise RuntimeError(timeout_notice) from exc
            finally:
                # 超时或客户端断开时，显式关闭生成器以尽快回收 CLI 子进程。
                with contextlib.suppress(Exception):
                    await stream.aclose()

        while emitted_chart_count < len(charts):
            yield {"event": "chart", "chart": charts[emitted_chart_count]}
            emitted_chart_count += 1

        final_text = (result_text or assistant_text or partial_text).strip()
        if not final_text and charts:
            final_text = "已根据系统数据生成图表。"
        if not final_text:
            raise RuntimeError(timeout_notice or "模型未返回可展示的回答")
        if timeout_notice:
            # 中断的结论可能不完整，必须显式标注，不能当作完整回答呈现。
            final_text = f"{final_text}\n\n> ⚠️ {timeout_notice}以上仅为已完成的部分结果，可能不完整。"

        # partial stream 已输出时，final 只负责确认和持久化；否则由前端直接使用 answer。
        yield {
            "event": "final",
            "answer": final_text,
            "charts": charts,
            "tool_trace": tool_trace,
            "model": model,
            "usage": usage,
            "streamed": bool(partial_text),
            "interrupted": bool(timeout_notice),
        }
