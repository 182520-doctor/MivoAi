"""In-memory coordination state for active Agent turns and model routing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.contexts.conversations.events import CodexEvent
from app.shared.model_routing import TextModelRoute


@dataclass(slots=True)
class ActiveTurn:
    """In-memory state for one currently streaming conversation turn."""

    queue: asyncio.Queue[CodexEvent | None]
    local_turn_id: str | None = None
    assistant_message_id: str | None = None
    stop_requested: bool = False
    thread_id: str | None = None
    turn_id: str | None = None
    task: asyncio.Task[None] | None = None
    route: TextModelRoute | None = None
    generation_task_id: str | None = None
    project_id: str | None = None
    workspace_path: str | None = None
