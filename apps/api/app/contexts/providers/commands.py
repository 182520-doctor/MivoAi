"""Application commands for provider configuration use cases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SaveCredentialCommand:
    api_key: str
    base_url: str | None


@dataclass(frozen=True, slots=True)
class UpdatePreferencesCommand:
    default_text_model_id: str | None
    default_image_model_id: str | None
    default_video_model_id: str | None
    agent_image_enabled: bool
    agent_video_enabled: bool
