"""HTTP schemas for provider endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.providers.commands import (
    SaveCredentialCommand,
    UpdatePreferencesCommand,
)


class ModelSelection(BaseModel):
    """Optional model routing metadata submitted with a chat message."""

    provider_id: str = Field(default="codex_local", alias="providerId", max_length=80)
    model_id: str | None = Field(default=None, alias="modelId", max_length=160)

    model_config = {"populate_by_name": True}


class CredentialUpsert(BaseModel):
    """A provider credential submitted by the local user."""

    api_key: str = Field(min_length=1, max_length=4096, alias="apiKey")
    base_url: str | None = Field(default=None, alias="baseUrl", max_length=500)

    model_config = {"populate_by_name": True}

    @field_validator("api_key")
    @classmethod
    def reject_blank_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("API Key 不能为空")
        return value.strip()

    def to_command(self) -> SaveCredentialCommand:
        return SaveCredentialCommand(api_key=self.api_key, base_url=self.base_url)


class PreferenceUpdate(BaseModel):
    """User-level model routing preferences for the single-user MVP."""

    default_text_model_id: str | None = Field(default=None, alias="defaultTextModelId")
    default_image_model_id: str | None = Field(default=None, alias="defaultImageModelId")
    default_video_model_id: str | None = Field(default=None, alias="defaultVideoModelId")
    agent_image_enabled: bool = Field(default=False, alias="agentImageEnabled")
    agent_video_enabled: bool = Field(default=False, alias="agentVideoEnabled")

    model_config = {"populate_by_name": True}

    def to_command(self) -> UpdatePreferencesCommand:
        return UpdatePreferencesCommand(
            default_text_model_id=self.default_text_model_id,
            default_image_model_id=self.default_image_model_id,
            default_video_model_id=self.default_video_model_id,
            agent_image_enabled=self.agent_image_enabled,
            agent_video_enabled=self.agent_video_enabled,
        )


class ProviderModelView(BaseModel):
    """Public catalog record. Secrets never appear in this response."""

    id: str
    provider_id: str = Field(alias="providerId")
    provider_name: str = Field(alias="providerName")
    name: str
    model_key: str = Field(alias="modelKey")
    capabilities: list[str]
    execution_mode: str = Field(alias="executionMode")
    enabled: bool
    configured: bool
    integration_status: str = Field(alias="integrationStatus")

    model_config = {"populate_by_name": True}


class ModelTestRequest(BaseModel):
    """A user-triggered text model connection test."""

    provider_id: str = Field(alias="providerId", max_length=80)
    prompt: str = Field(
        default="只回复：模型连接正常",
        min_length=1,
        max_length=500,
    )

    model_config = {"populate_by_name": True}
