"""Claude Agent SDK 运行时设置的读取、校验和持久化。"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AISettings, User
from app.models.ai_schemas import (
    AIConnectionTestRequest,
    AIConnectionTestResponse,
    AISettingsUpdate,
    AISettingsView,
)


DEFAULT_SYSTEM_PROMPT = """你是 CostMatrix 的成本效能分析 Agent，服务于系统操作人员。

工作规则：
1. 涉及系统数据的事实必须先调用数据库工具核实，不得编造数字。
2. 数据库工具只读。先查看表和字段，再编写兼容当前数据库的 SELECT 查询。
3. 可以访问全部业务数据，但不得查询、推断或展示密码哈希、API Key 等认证机密。
4. 用户要求图表，或图表明显有助于比较、趋势、分布时，必须调用 create_echarts_chart。
5. 图表标题、图例、坐标轴和结论应使用用户当前语言；金额默认注明人民币元。
6. 回复中简洁说明数据口径、关键结论以及异常或缺失值，不要展示冗长 SQL。
7. 仅回答 CostMatrix 内的行政、考勤、差旅、项目、部门、异常与成本效能相关问题。
"""


PROVIDER_DEFAULTS = {
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-6",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/anthropic",
        "model": "deepseek-chat",
    },
    "aliyun_beijing": {
        "base_url": "https://dashscope.aliyuncs.com/apps/anthropic",
        "model": "",
    },
    "aliyun_workspace": {
        "base_url": "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/apps/anthropic",
        "model": "",
    },
    "aliyun_singapore": {
        "base_url": "https://dashscope-intl.aliyuncs.com/apps/anthropic",
        "model": "",
    },
    "aliyun_token_plan": {
        "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic",
        "model": "",
    },
    "aliyun_coding_plan": {
        "base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic",
        "model": "",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/anthropic",
        "model": "",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/anthropic",
        "model": "",
    },
    "minimax": {
        "base_url": "https://api.minimaxi.com/anthropic",
        "model": "",
    },
    "stepfun": {
        "base_url": "https://api.stepfun.com",
        "model": "",
    },
    "stepfun_plan": {
        "base_url": "https://api.stepfun.com/step_plan",
        "model": "",
    },
    "xiaomi": {
        "base_url": "https://api.xiaomimimo.com/anthropic",
        "model": "",
    },
    "tencent": {
        "base_url": "https://api.hunyuan.cloud.tencent.com/anthropic",
        "model": "",
    },
    "custom": {
        "base_url": "",
        "model": "",
    },
}


@dataclass(frozen=True)
class EffectiveAISettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    max_turns: int
    request_timeout_seconds: int
    total_timeout_seconds: int
    max_result_rows: int
    system_prompt: str


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        # SECRET_KEY 变化后旧密文不可恢复；不要把密文误当成 API Key 使用。
        return ""


def _get_row(db: Session) -> Optional[AISettings]:
    return db.query(AISettings).filter(AISettings.id == 1).first()


def _env_base_url(provider: str) -> str:
    return settings.anthropic_base_url.strip() or PROVIDER_DEFAULTS[provider]["base_url"]


def _env_model(provider: str) -> str:
    configured = settings.anthropic_model.strip()
    if provider == settings.anthropic_provider and configured:
        return configured
    return PROVIDER_DEFAULTS[provider]["model"] or configured


def get_effective(db: Session) -> EffectiveAISettings:
    row = _get_row(db)
    provider = (row.provider if row and row.provider else settings.anthropic_provider).strip().lower()
    if provider not in PROVIDER_DEFAULTS:
        provider = "anthropic"

    api_key = (
        _decrypt_secret(row.encrypted_api_key)
        if row and row.encrypted_api_key
        else settings.anthropic_api_key.strip()
    )
    base_url = (
        row.base_url.strip()
        if row and row.base_url is not None
        else _env_base_url(provider)
    )
    model = (
        row.model.strip()
        if row and row.model is not None
        else _env_model(provider)
    )
    max_turns = (
        row.max_turns
        if row and row.max_turns is not None
        else settings.anthropic_max_turns
    )
    request_timeout_seconds = (
        row.request_timeout_seconds
        if row and row.request_timeout_seconds is not None
        else settings.anthropic_request_timeout_seconds
    )
    max_result_rows = (
        row.max_result_rows
        if row and row.max_result_rows is not None
        else settings.agent_max_result_rows
    )
    system_prompt = (
        row.system_prompt.strip()
        if row and row.system_prompt is not None and row.system_prompt.strip()
        else DEFAULT_SYSTEM_PROMPT
    )

    return EffectiveAISettings(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_turns=int(max_turns),
        request_timeout_seconds=int(request_timeout_seconds),
        total_timeout_seconds=int(settings.agent_total_timeout_seconds),
        max_result_rows=int(max_result_rows),
        system_prompt=system_prompt,
    )


def describe(db: Session) -> AISettingsView:
    row = _get_row(db)
    effective = get_effective(db)
    runtime_fields = {
        "provider": bool(row and row.provider is not None),
        "api_key": bool(row and row.encrypted_api_key),
        "base_url": bool(row and row.base_url is not None),
        "model": bool(row and row.model is not None),
        "max_turns": bool(row and row.max_turns is not None),
        "request_timeout_seconds": bool(row and row.request_timeout_seconds is not None),
        "max_result_rows": bool(row and row.max_result_rows is not None),
        "system_prompt": bool(row and row.system_prompt is not None),
    }
    sources: Dict[str, str] = {
        key: ("database" if is_runtime else "environment")
        for key, is_runtime in runtime_fields.items()
    }
    if not effective.api_key:
        sources["api_key"] = "unset"

    return AISettingsView(
        provider=effective.provider,
        base_url=effective.base_url,
        model=effective.model,
        max_turns=effective.max_turns,
        request_timeout_seconds=effective.request_timeout_seconds,
        max_result_rows=effective.max_result_rows,
        system_prompt=effective.system_prompt,
        api_key_set=bool(effective.api_key),
        sources=sources,
        updated_at=row.updated_at if row else None,
    )


def _validate_post_save(effective: EffectiveAISettings) -> None:
    if not effective.base_url:
        raise ValueError("必须填写 Base URL")
    if not effective.model:
        raise ValueError("必须填写模型")
    if effective.base_url and not effective.base_url.startswith(("http://", "https://")):
        raise ValueError("Base URL 必须以 http:// 或 https:// 开头")


def save(db: Session, payload: AISettingsUpdate, updated_by: User) -> AISettingsView:
    row = _get_row(db) or AISettings(id=1)
    changes = payload.model_dump(exclude_unset=True)

    if "provider" in changes and changes["provider"] is not None:
        row.provider = changes["provider"]
    if "api_key" in changes and changes["api_key"] is not None:
        secret = changes["api_key"].strip()
        if secret:
            row.encrypted_api_key = _encrypt_secret(secret)
    if "base_url" in changes and changes["base_url"] is not None:
        row.base_url = changes["base_url"].strip()
    if "model" in changes and changes["model"] is not None:
        row.model = changes["model"].strip()
    if "max_turns" in changes and changes["max_turns"] is not None:
        row.max_turns = changes["max_turns"]
    if (
        "request_timeout_seconds" in changes
        and changes["request_timeout_seconds"] is not None
    ):
        row.request_timeout_seconds = changes["request_timeout_seconds"]
    if "max_result_rows" in changes and changes["max_result_rows"] is not None:
        row.max_result_rows = changes["max_result_rows"]
    if "system_prompt" in changes and changes["system_prompt"] is not None:
        row.system_prompt = changes["system_prompt"].strip()

    row.updated_by = updated_by.id
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.flush()
    _validate_post_save(get_effective(db))
    db.commit()
    return describe(db)


def reset(db: Session) -> AISettingsView:
    row = _get_row(db)
    if row:
        db.delete(row)
        db.commit()
    return describe(db)


def _messages_endpoint(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/v1/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"


def prepare_connection_test(
    db: Session,
    payload: AIConnectionTestRequest,
) -> EffectiveAISettings:
    """将未保存的表单值与当前密钥合并，不修改数据库。"""
    current = get_effective(db)
    api_key = (payload.api_key or "").strip() or current.api_key
    candidate = replace(
        current,
        provider=payload.provider,
        api_key=api_key,
        base_url=payload.base_url.strip(),
        model=payload.model.strip(),
    )
    _validate_post_save(candidate)
    if not candidate.api_key:
        raise ValueError("请先填写 API Key，或保存一个可复用的 API Key")
    if "{" in candidate.base_url or "}" in candidate.base_url:
        raise ValueError("请先将 Base URL 中的占位符替换为实际值")
    return candidate


def test_connection(
    candidate: EffectiveAISettings,
) -> AIConnectionTestResponse:
    """使用最小 Anthropic Messages 请求验证地址、密钥与模型。"""
    endpoint = _messages_endpoint(candidate.base_url)
    body = json.dumps(
        {
            "model": candidate.model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Reply with OK."}],
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": candidate.api_key,
            "Authorization": f"Bearer {candidate.api_key}",
            "User-Agent": "CostMatrix-Connection-Test/1.0",
        },
    )
    started = time.monotonic()
    try:
        with urlopen(
            request,
            timeout=min(candidate.request_timeout_seconds, 30),
        ) as response:
            response.read(2048)
            latency_ms = round((time.monotonic() - started) * 1000)
            return AIConnectionTestResponse(
                success=True,
                message="连接成功，Base URL、API Key 与模型均可用",
                latency_ms=latency_ms,
                endpoint=endpoint,
            )
    except HTTPError as exc:
        raw_detail = exc.read(4096).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_detail)
            detail = (
                parsed.get("error", {}).get("message")
                if isinstance(parsed.get("error"), dict)
                else parsed.get("message") or parsed.get("error")
            )
        except (json.JSONDecodeError, AttributeError):
            detail = raw_detail
        detail = str(detail or exc.reason).strip()[:500]
        raise ValueError(f"模型服务返回 HTTP {exc.code}：{detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ValueError(f"无法连接模型服务：{reason}") from exc
