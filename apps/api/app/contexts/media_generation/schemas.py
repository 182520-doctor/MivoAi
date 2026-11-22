"""HTTP schemas for media generation requests."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.contexts.media_generation.commands import CreateGenerationCommand


class GenerationCreate(BaseModel):
    """A provider-neutral media generation request."""

    provider_id: str = Field(default="volcengine", alias="providerId", max_length=80)
    model_id: str = Field(alias="modelId", max_length=160)
    task_type: str = Field(alias="taskType", max_length=60)
    prompt: str = Field(default="", max_length=12000)
    session_id: str | None = Field(default=None, alias="sessionId", max_length=80)
    turn_id: str | None = Field(default=None, alias="turnId", max_length=80)
    input_asset_ids: list[str] = Field(
        default_factory=list,
        alias="inputAssetIds",
        max_length=64,
    )
    images: list[str] = Field(default_factory=list, max_length=64)
    videos: list[str] = Field(default_factory=list, max_length=64)
    audios: list[str] = Field(default_factory=list, max_length=64)
    files: list[str] = Field(default_factory=list, max_length=64)
    parameters: dict[str, object] = Field(default_factory=dict)
    client_request_id: str | None = Field(
        default=None, alias="clientRequestId", max_length=120
    )

    model_config = {"populate_by_name": True}

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        return value.strip()

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        allowed = {
            "image_generation",
            "image_processing",
            "video_generation",
            "video_processing",
            "audio_processing",
            "transcription",
        }
        if value not in allowed:
            raise ValueError(
                "当前仅支持 image_generation、image_processing、video_generation、"
                "video_processing、audio_processing 和 transcription"
            )
        return value

    def to_command(self) -> CreateGenerationCommand:
        images = self.images or self.input_asset_ids
        return CreateGenerationCommand(
            provider_id=self.provider_id,
            model_id=self.model_id,
            task_type=self.task_type,
            prompt=self.prompt,
            session_id=self.session_id,
            turn_id=self.turn_id,
            input_asset_ids=images,
            reference_asset_ids={
                "image": images,
                "video": self.videos,
                "audio": self.audios,
                "file": self.files,
            },
            parameters=self.parameters,
            client_request_id=self.client_request_id,
            raw_request=self.model_dump(by_alias=True),
        )


class GenerationRetryBatch(BaseModel):
    task_ids: list[str] = Field(
        alias="taskIds",
        min_length=1,
        max_length=50,
    )

    model_config = {"populate_by_name": True}
