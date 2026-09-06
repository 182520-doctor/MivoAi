"""Reusable integration fakes implementing the CodexClient contract."""

from collections.abc import AsyncIterator
from typing import Any

from app.models.codex import CodexEvent


class FakeCodexClient:
    def __init__(self) -> None:
        self.running = False

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False

    async def create_thread(self) -> str:
        return "test-thread"

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        return {"data": [], "nextCursor": None}

    async def chat(
        self, message: str, thread_id: str | None
    ) -> AsyncIterator[CodexEvent]:
        yield {
            "type": "meta",
            "threadId": thread_id or "test-thread",
            "turnId": "test-turn",
        }
        yield {"type": "reasoning_started", "text": ""}
        yield {"type": "reasoning_delta", "text": "先理解用户需求。"}
        yield {"type": "reasoning_usage", "tokens": 12}
        yield {"type": "delta", "text": message}
        yield {"type": "message_completed", "text": message}
        yield {"type": "done", "status": "completed"}

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "authenticated": True,
            "version": "codex-test/0.1.0",
            "platform": "macos",
            "binary": "/test/codex",
        }
