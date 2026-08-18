"""CostMatrix 单 Agent 对话、会话与模型设置 API。"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.cost_agent import CostMatrixAgent
from app.db.database import SessionLocal, get_db
from app.db.models import AIConversation, AIMessage, User
from app.models.ai_schemas import (
    AgentChatRequest,
    AIConnectionTestRequest,
    AIConnectionTestResponse,
    AISettingsUpdate,
    AISettingsView,
    ConversationCreateRequest,
    ConversationItem,
    ConversationMessagesResponse,
    ConversationUpdateRequest,
    MessageItem,
)
from app.services import ai_settings_service
from app.services.auth_service import get_current_user, require_admin
from app.utils.logger import get_logger


router = APIRouter()
logger = get_logger("api.agent_routes")


def _conversation_item(row: AIConversation) -> ConversationItem:
    return ConversationItem(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _json_list(value: str | None) -> List[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _owned_conversation(
    db: Session,
    conversation_id: str,
    user: User,
) -> AIConversation:
    row = (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="对话不存在")
    return row


@router.get(
    "/agent/conversations",
    response_model=List[ConversationItem],
    tags=["ai-agent"],
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AIConversation)
        .filter(AIConversation.user_id == current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .all()
    )
    return [_conversation_item(row) for row in rows]


@router.post(
    "/agent/conversations",
    response_model=ConversationItem,
    tags=["ai-agent"],
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = AIConversation(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=payload.title.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _conversation_item(row)


@router.get(
    "/agent/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    tags=["ai-agent"],
)
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, current_user)
    rows = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc(), AIMessage.id.asc())
        .all()
    )
    return ConversationMessagesResponse(
        conversation=_conversation_item(conversation),
        messages=[
            MessageItem(
                id=row.id,
                role=row.role,
                content=row.content,
                charts=_json_list(row.charts_json),
                tool_trace=_json_list(row.tool_trace_json),
                model=row.model,
                provider=row.provider,
                route_slot=row.route_slot,
                duration_ms=row.duration_ms,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.patch(
    "/agent/conversations/{conversation_id}",
    response_model=ConversationItem,
    tags=["ai-agent"],
)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, current_user)
    conversation.title = payload.title.strip()
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _conversation_item(conversation)


@router.delete(
    "/agent/conversations/{conversation_id}",
    tags=["ai-agent"],
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, conversation_id, current_user)
    db.query(AIMessage).filter(
        AIMessage.conversation_id == conversation_id
    ).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()
    return {"success": True, "message": "对话已删除"}


@router.post("/agent/chat/stream", tags=["ai-agent"])
async def stream_agent_chat(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation: AIConversation
    if payload.conversation_id:
        conversation = _owned_conversation(db, payload.conversation_id, current_user)
    else:
        conversation = AIConversation(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=payload.message[:36],
        )
        db.add(conversation)
        db.flush()

    history_rows = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation.id)
        .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
        .limit(12)
        .all()
    )
    history = [
        {"role": row.role, "content": row.content}
        for row in reversed(history_rows)
        if row.role in {"user", "assistant"}
    ]

    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
        )
    )
    if conversation.title == "新对话":
        conversation.title = payload.message[:36]
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()

    conversation_id = conversation.id
    conversation_title = conversation.title
    runtime_settings = ai_settings_service.get_effective(db)

    def persist_final_answer(final_payload: Dict[str, Any]) -> None:
        with SessionLocal() as persist_db:
            persist_db.add(
                AIMessage(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=str(final_payload.get("answer") or ""),
                    charts_json=json.dumps(
                        final_payload.get("charts") or [],
                        ensure_ascii=False,
                        default=str,
                    ),
                    tool_trace_json=json.dumps(
                        final_payload.get("tool_trace") or [],
                        ensure_ascii=False,
                        default=str,
                    ),
                    model=str(final_payload.get("model") or "") or None,
                    provider=str(final_payload.get("provider") or "") or None,
                    route_slot=str(final_payload.get("route_slot") or "") or None,
                    duration_ms=(
                        int(final_payload["duration_ms"])
                        if isinstance(final_payload.get("duration_ms"), (int, float))
                        else None
                    ),
                )
            )
            persisted_conversation = (
                persist_db.query(AIConversation)
                .filter(AIConversation.id == conversation_id)
                .first()
            )
            if persisted_conversation:
                persisted_conversation.updated_at = datetime.utcnow()
                persist_db.add(persisted_conversation)
            persist_db.commit()

    async def generate():
        yield _sse(
            {
                "event": "conversation",
                "conversation_id": conversation_id,
                "title": conversation_title,
                "agent": "CostMatrix Agent",
            }
        )
        try:
            async for event in CostMatrixAgent().run_stream(
                user_message=payload.message,
                history=history,
                runtime_settings=runtime_settings,
            ):
                if event.get("event") == "final":
                    if event.get("interrupted"):
                        logger.warning(
                            "Agent run interrupted by timeout, partial answer kept: "
                            f"conversation={conversation_id}"
                        )
                    try:
                        persist_final_answer(event)
                    except Exception as exc:
                        logger.exception(
                            "Failed to persist Agent answer: "
                            f"conversation={conversation_id}: {exc}"
                        )
                yield _sse(event)
        except asyncio.CancelledError:
            logger.info(f"Agent stream cancelled: conversation={conversation_id}")
            raise
        except Exception as exc:
            logger.exception(f"Agent stream failed: conversation={conversation_id}: {exc}")
            yield _sse({"event": "error", "message": str(exc)})
            return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/ai-settings",
    response_model=AISettingsView,
    tags=["ai-settings"],
)
async def get_ai_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ai_settings_service.describe(db)


@router.put(
    "/ai-settings",
    response_model=AISettingsView,
    tags=["ai-settings"],
)
async def update_ai_settings(
    payload: AISettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return ai_settings_service.save(db, payload, current_user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/ai-settings",
    response_model=AISettingsView,
    tags=["ai-settings"],
)
async def reset_ai_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ai_settings_service.reset(db)


@router.post(
    "/ai-settings/test",
    response_model=AIConnectionTestResponse,
    tags=["ai-settings"],
)
async def test_ai_settings(
    payload: AIConnectionTestRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        candidate = ai_settings_service.prepare_connection_test(db, payload)
        return await asyncio.to_thread(ai_settings_service.test_connection, candidate)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
