"""Structural contracts between business services and external integrations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.models.codex import CodexEvent


class CodexClient(Protocol):
    """Operations the application requires from a Codex App Server client."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def create_thread(self) -> str: ...

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]: ...

    def chat(self, message: str, thread_id: str | None) -> AsyncIterator[CodexEvent]: ...

    def status(self) -> dict[str, Any]: ...
