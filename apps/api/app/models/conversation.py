"""Conversation request models and internal runtime state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from app.models.codex import CodexEvent


class MessageCreate(BaseModel):
    """Validated payload submitted by the browser for a new Agent turn."""

    message: str = Field(min_length=1, max_length=8000)
    clientMessageId: str = Field(min_length=1, max_length=100)
    providerId: str = Field(default="codex_local", max_length=80)
    modelId: str | None = Field(default=None, max_length=160)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        """Reject whitespace-only content and normalize surrounding whitespace."""

        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()


class LegacyChatRequest(BaseModel):
    """Schema retained only so the removed legacy endpoint still validates input."""

    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None


@dataclass(frozen=True, slots=True)
class Conversation:
    """Persistence-neutral representation of a local conversation record."""

    id: str
    title: str
    thread_id: str | None
    status: str = "idle"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """One locally persisted chat message rendered by the browser."""

    id: str
    session_id: str
    role: str
    content: str
    status: str
    turn_id: str | None = None
    reasoning: str = ""
    reasoning_tokens: int = 0


@dataclass(frozen=True, slots=True)
class TurnRecord:
    """Identifiers allocated before a browser stream starts."""

    id: str
    user_message_id: str
    assistant_message_id: str


@dataclass(slots=True)
class ActiveTurn:
    """In-memory coordination state for one currently streaming conversation."""

    queue: asyncio.Queue[CodexEvent | None]
    local_turn_id: str | None = None
    assistant_message_id: str | None = None
    stop_requested: bool = False
    thread_id: str | None = None
    turn_id: str | None = None
    task: asyncio.Task[None] | None = None
    provider_id: str = "codex_local"
    model_id: str = "codex-local-default"
    provider_model: dict[str, object] | None = None
    generation_task_id: str | None = None
