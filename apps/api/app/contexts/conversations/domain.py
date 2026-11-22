"""Conversation aggregates and persistence-neutral read models."""

from __future__ import annotations

from dataclasses import dataclass

TOOL_RUNTIME_VERSION = 23


@dataclass(frozen=True, slots=True)
class Conversation:
    """A local product conversation, distinct from a Codex thread."""

    id: str
    title: str
    thread_id: str | None
    status: str = "idle"
    tool_runtime_version: int = 0
    workspace_path: str | None = None
    project_id: str | None = None
    episode_id: str | None = None
    scope: str | None = None
    message_count: int = 0
    last_activity_at: str | None = None


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
