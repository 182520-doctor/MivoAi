"""Ports required by the conversation application from Agent runtimes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol

from app.modules.conversations.domain import (
    Conversation,
    ConversationMessage,
    TurnRecord,
)
from app.modules.conversations.events import CodexEvent
from app.shared.model_routing import TextModelRoute


class CodexClient(Protocol):
    """Operations the application requires from a Codex App Server client."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def create_thread(
        self,
        workspace: Path | None = None,
        *,
        cwd: Path | None = None,
        shared_roots: list[Path] | None = None,
    ) -> str: ...

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]: ...

    def chat(
        self,
        message: str,
        thread_id: str | None,
        workspace: Path | None = None,
        *,
        cwd: Path | None = None,
        shared_roots: list[Path] | None = None,
    ) -> AsyncIterator[CodexEvent]: ...

    def status(self) -> dict[str, Any]: ...


class ConversationModelGateway(Protocol):
    """Cross-context port for text model resolution and external streaming."""

    def resolve_text_route(
        self, requested_provider_id: str, requested_model_id: str | None
    ) -> TextModelRoute: ...

    def stream_text(
        self, route: TextModelRoute, message: str
    ) -> AsyncIterator[CodexEvent]: ...


class ConversationTaskRecorder(Protocol):
    """Cross-context port for auditable text generation tasks."""

    def start_text_task(
        self,
        *,
        conversation_id: str,
        turn_id: str,
        prompt: str,
        original_request: dict[str, object],
        route: TextModelRoute,
        client_request_id: str,
    ) -> str: ...

    def update_text_task_request(
        self, task_id: str, provider_request: dict[str, object]
    ) -> None: ...

    def finish_text_task(
        self,
        task_id: str,
        *,
        status: str,
        route: TextModelRoute,
        error: str | None = None,
    ) -> None: ...


class CreativeProjectGateway(Protocol):
    """Optional bridge to the long-lived creative-project workspace."""

    def get_project(self, project_id: str) -> dict[str, Any] | None: ...

    def get_thread(self, project_id: str) -> str | None: ...

    def attach_thread(self, project_id: str, codex_thread_id: str) -> None: ...

    def reconcile_workspace(self, project_id: str) -> dict[str, object]: ...


class ConversationWorkspacePort(Protocol):
    """Filesystem operations required by a conversation."""

    shared_root: Path

    def initialize(self) -> None: ...

    def ensure(self, conversation_id: str) -> Path: ...


class ConversationWorkspaceQualityGate(Protocol):
    """Optional quality inspection for creative-project workspaces."""

    def inspect(self, workspace: Path) -> dict[str, object]: ...

    def write_report(
        self,
        workspace: Path,
        quality: dict[str, object],
    ) -> None: ...


class ConversationRepositoryPort(Protocol):
    """Persistence operations required by the conversation application."""

    def list_conversations(self) -> list[Conversation]: ...

    def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    def create_conversation(
        self,
        title: str = "新的创意对话",
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        scope: str | None = None,
    ) -> Conversation: ...

    def attach_thread(
        self,
        conversation_id: str,
        thread_id: str,
        title: str,
        tool_runtime_version: int = 0,
    ) -> None: ...

    def set_workspace(self, conversation_id: str, workspace_path: str) -> None: ...

    def list_messages(self, conversation_id: str) -> list[ConversationMessage]: ...

    def create_turn_with_messages(
        self, conversation_id: str, client_message_id: str, user_content: str
    ) -> TurnRecord: ...

    def set_codex_turn(self, local_turn_id: str, codex_turn_id: str) -> None: ...

    def append_assistant_content(self, message_id: str, delta: str) -> None: ...

    def replace_assistant_content(self, message_id: str, content: str) -> None: ...

    def append_reasoning(self, turn_id: str, delta: str) -> None: ...

    def replace_reasoning(self, turn_id: str, text: str) -> None: ...

    def update_reasoning_tokens(self, turn_id: str, tokens: int) -> None: ...

    def finish_turn(
        self,
        conversation_id: str,
        turn_id: str,
        assistant_message_id: str,
        status: str,
        error: str | None = None,
    ) -> None: ...

    def recover_interrupted_turns(self) -> int: ...

    def submission_exists(self, client_message_id: str) -> bool: ...

    def start_submission(self, client_message_id: str, conversation_id: str) -> None: ...

    def finish_submission(self, client_message_id: str) -> None: ...
