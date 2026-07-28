"""单 Agent 流式接口与最终消息持久化测试。"""
import json

from fastapi.testclient import TestClient

from app.agents.cost_agent import CostMatrixAgent
from app.main import app


def test_stream_creates_conversation_and_persists_final_before_completion(monkeypatch):
    async def fake_run_stream(self, **kwargs):
        yield {"event": "status", "phase": "thinking", "message": "测试查询"}
        yield {
            "event": "final",
            "answer": "研发中心成本最高。",
            "charts": [
                {
                    "chart_type": "bar",
                    "title": "部门成本",
                    "subtitle": None,
                    "echarts_option": {
                        "xAxis": {"type": "category", "data": ["研发中心"]},
                        "yAxis": {"type": "value"},
                        "series": [{"type": "bar", "data": [100]}],
                    },
                }
            ],
            "tool_trace": [{"tool": "execute_readonly_sql", "duration_ms": 5}],
            "model": "test-model",
            "usage": {},
            "streamed": False,
        }

    monkeypatch.setattr(CostMatrixAgent, "run_stream", fake_run_stream)

    with TestClient(app) as client:
        login = client.post(
            "/api/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.post(
            "/api/agent/chat/stream",
            headers=headers,
            json={"message": "分析部门成本"},
        )
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        conversation_id = events[0]["conversation_id"]
        assert [event["event"] for event in events] == [
            "conversation",
            "status",
            "final",
        ]

        persisted = client.get(
            f"/api/agent/conversations/{conversation_id}/messages",
            headers=headers,
        )
        assert persisted.status_code == 200
        messages = persisted.json()["messages"]
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[-1]["content"] == "研发中心成本最高。"
        assert messages[-1]["charts"][0]["echarts_option"]["series"][0]["data"] == [100]


def test_agent_routes_require_authentication():
    with TestClient(app) as client:
        assert client.get("/api/agent/conversations").status_code == 401
        assert client.get("/api/ai-settings").status_code == 401
