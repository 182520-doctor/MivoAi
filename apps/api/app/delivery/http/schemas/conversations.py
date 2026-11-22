"""HTTP schemas for conversation endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.conversations.commands import SendMessageCommand


class ConversationCreate(BaseModel):
    project_id: str | None = Field(
        default=None,
        alias="projectId",
        max_length=80,
    )
    episode_id: str | None = Field(
        default=None,
        alias="episodeId",
        max_length=80,
    )
    scope: str | None = Field(default=None, max_length=40)

    model_config = {"populate_by_name": True}


class MessageCreate(BaseModel):
    """Validated payload submitted by the browser for a new Agent turn."""

    message: str = Field(min_length=1, max_length=8000)
    clientMessageId: str = Field(min_length=1, max_length=100)
    providerId: str = Field(default="codex_local", max_length=80)
    modelId: str | None = Field(default=None, max_length=160)
    projectId: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        """Reject whitespace-only content and normalize surrounding whitespace."""

        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()

    def to_command(self) -> SendMessageCommand:
        return SendMessageCommand(
            message=self.message,
            client_message_id=self.clientMessageId,
            provider_id=self.providerId,
            model_id=self.modelId,
            creative_project_id=self.projectId,
            raw_request=self.model_dump(by_alias=True),
        )


class LegacyChatRequest(BaseModel):
    """Schema retained only so the removed legacy endpoint still validates input."""

    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None
