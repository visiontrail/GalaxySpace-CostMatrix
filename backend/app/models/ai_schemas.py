"""Claude Agent SDK 对话与设置接口模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ChartSpec(BaseModel):
    """前后端统一的 ECharts 图表协议。"""

    chart_type: str
    title: str
    subtitle: Optional[str] = None
    echarts_option: Dict[str, Any]


class AgentChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, max_length=36)
    message: str = Field(..., min_length=1, max_length=20_000)

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("消息不能为空")
        return cleaned


class ConversationCreateRequest(BaseModel):
    title: str = Field("新对话", min_length=1, max_length=120)


class ConversationUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class ConversationItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    charts: List[ChartSpec] = Field(default_factory=list)
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationItem
    messages: List[MessageItem]


class AISettingsUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = Field(None, max_length=20_000)
    base_url: Optional[str] = Field(None, max_length=500)
    model: Optional[str] = Field(None, max_length=200)
    max_turns: Optional[int] = Field(None, ge=1, le=50)
    request_timeout_seconds: Optional[int] = Field(None, ge=30, le=900)
    max_result_rows: Optional[int] = Field(None, ge=10, le=5_000)
    system_prompt: Optional[str] = Field(None, max_length=20_000)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        provider = value.strip().lower()
        supported_providers = {
            "anthropic",
            "deepseek",
            "aliyun_beijing",
            "aliyun_workspace",
            "aliyun_singapore",
            "aliyun_token_plan",
            "aliyun_coding_plan",
            "zhipu",
            "kimi",
            "minimax",
            "stepfun",
            "stepfun_plan",
            "xiaomi",
            "tencent",
            "custom",
        }
        if provider not in supported_providers:
            raise ValueError("不支持该模型服务商")
        return provider


class AISettingsView(BaseModel):
    provider: str
    base_url: str
    model: str
    max_turns: int
    request_timeout_seconds: int
    max_result_rows: int
    system_prompt: str
    api_key_set: bool
    sources: Dict[str, str]
    updated_at: Optional[datetime] = None


class AIConnectionTestRequest(BaseModel):
    """测试表单中的连接参数；API Key 留空时使用当前已保存值。"""

    provider: str
    api_key: Optional[str] = Field(None, max_length=20_000)
    base_url: str = Field(..., min_length=1, max_length=500)
    model: str = Field(..., min_length=1, max_length=200)

    _validate_provider = field_validator("provider")(
        AISettingsUpdate.validate_provider.__func__
    )


class AIConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int
    endpoint: str
