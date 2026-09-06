"""Schemas for the provider/model gateway and user preferences."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


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


class PreferenceUpdate(BaseModel):
    """User-level model routing preferences for the single-user MVP."""

    default_text_model_id: str | None = Field(default=None, alias="defaultTextModelId")
    default_image_model_id: str | None = Field(default=None, alias="defaultImageModelId")
    default_video_model_id: str | None = Field(default=None, alias="defaultVideoModelId")
    agent_image_enabled: bool = Field(default=False, alias="agentImageEnabled")
    agent_video_enabled: bool = Field(default=False, alias="agentVideoEnabled")

    model_config = {"populate_by_name": True}


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


class GenerationCreate(BaseModel):
    """A provider-neutral media generation request."""

    provider_id: str = Field(default="volcengine", alias="providerId", max_length=80)
    model_id: str = Field(alias="modelId", max_length=160)
    task_type: str = Field(alias="taskType", max_length=60)
    prompt: str = Field(min_length=1, max_length=12000)
    session_id: str | None = Field(default=None, alias="sessionId", max_length=80)
    turn_id: str | None = Field(default=None, alias="turnId", max_length=80)
    input_asset_ids: list[str] = Field(default_factory=list, alias="inputAssetIds", max_length=16)
    parameters: dict[str, object] = Field(default_factory=dict)
    client_request_id: str | None = Field(
        default=None, alias="clientRequestId", max_length=120
    )

    model_config = {"populate_by_name": True}

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("提示词不能为空")
        return value.strip()

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        allowed = {"image_generation", "video_generation"}
        if value not in allowed:
            raise ValueError("当前仅支持 image_generation 和 video_generation")
        return value
