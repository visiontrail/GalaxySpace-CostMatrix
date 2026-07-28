"""Claude Agent 结构化 ECharts 图表工具。"""
from __future__ import annotations

import json
from typing import Any, Dict, List


ALLOWED_CHART_TYPES = {
    "bar",
    "line",
    "pie",
    "area",
    "stacked_bar",
    "stacked_line",
    "scatter",
    "radar",
    "funnel",
    "gauge",
    "heatmap",
    "treemap",
    "sankey",
    "sunburst",
    "boxplot",
    "graph",
    "parallel",
    "table",
}
MAX_CHART_BYTES = 500_000


def validate_chart_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    chart_type = str(payload.get("chart_type") or "").strip()
    title = str(payload.get("title") or "").strip()
    option = payload.get("echarts_option")
    subtitle = str(payload.get("subtitle") or "").strip() or None

    if chart_type not in ALLOWED_CHART_TYPES:
        raise ValueError(f"不支持的图表类型：{chart_type}")
    if not title:
        raise ValueError("图表标题不能为空")
    if not isinstance(option, dict):
        raise ValueError("echarts_option 必须是 JSON 对象")
    if not any(key in option for key in ("series", "xAxis", "yAxis", "dataset")):
        raise ValueError("echarts_option 缺少 series、坐标轴或 dataset")

    encoded = json.dumps(option, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_CHART_BYTES:
        raise ValueError("图表配置过大")

    return {
        "chart_type": chart_type,
        "title": title,
        "subtitle": subtitle,
        "echarts_option": option,
    }


def build_chart_mcp_server(charts: List[Dict[str, Any]]) -> tuple[Any, str]:
    try:
        from claude_agent_sdk import create_sdk_mcp_server, tool
    except ImportError as exc:
        raise RuntimeError(
            "Claude Agent SDK 未安装，请执行 pip install -r requirements.txt"
        ) from exc

    @tool(
        "create_echarts_chart",
        (
            "创建一个可在前端交互渲染的 ECharts 图表。"
            "echarts_option 必须是完整、纯 JSON 的 ECharts option，不能包含 JavaScript 函数。"
        ),
        {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": sorted(ALLOWED_CHART_TYPES),
                },
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "echarts_option": {"type": "object"},
            },
            "required": ["chart_type", "title", "echarts_option"],
        },
    )
    async def create_echarts_chart(args):
        try:
            spec = validate_chart_spec(args)
            charts.append(spec)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"status": "created", "title": spec["title"]},
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        except ValueError as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "is_error": True,
            }

    server_name = "costmatrix_chart"
    server = create_sdk_mcp_server(
        name=server_name,
        version="1.0.0",
        tools=[create_echarts_chart],
    )
    return server, f"mcp__{server_name}__create_echarts_chart"
