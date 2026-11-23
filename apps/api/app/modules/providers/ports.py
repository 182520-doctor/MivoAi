"""Ports required by provider routing from persistence and text adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.modules.conversations.events import CodexEvent


class ProviderRepositoryPort(Protocol):
    """Persistence operations used by provider routing."""

    def list_models(self) -> list[dict[str, object]]: ...

    def save_credential(
        self,
        *,
        provider_id: str,
        credential_id: str,
        encrypted_secret: str,
        config_json: str,
        updated_at: str,
        name: str,
    ) -> bool: ...

    def get_preferences(self) -> dict[str, object] | None: ...

    def update_preferences(
        self,
        *,
        default_text_model_id: str | None,
        default_image_model_id: str | None,
        default_video_model_id: str | None,
        agent_image_enabled: bool,
        agent_video_enabled: bool,
    ) -> None: ...

    def resolve_text_model(
        self, requested_model_id: str | None
    ) -> dict[str, object] | None: ...

    def resolve_media_model(self, model_id: str) -> dict[str, object] | None: ...


class TextChatPort(Protocol):
    """Streaming text adapter used by the provider gateway."""

    def chat(
        self, *, api_key: str, base_url: str, model: str, message: str
    ) -> AsyncIterator[CodexEvent]: ...
