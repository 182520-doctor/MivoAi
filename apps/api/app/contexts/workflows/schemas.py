"""HTTP schemas for ComfyUI workflow discovery and testing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkflowImportRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500, alias="filename")
    name: str | None = Field(default=None, max_length=160, alias="name")
    capability: Literal[
        "image_generation",
        "image_processing",
        "video_generation",
        "video_processing",
        "audio_processing",
        "transcription",
    ] = Field(alias="capability")

    model_config = {"populate_by_name": True}


class WorkflowTestRequest(BaseModel):
    prompt: str = Field(
        default="A cinematic product image, soft studio lighting, highly detailed",
        min_length=1,
        max_length=4000,
    )
    asset_ids: list[str] = Field(default_factory=list, alias="assetIds")

    model_config = {"populate_by_name": True}


class WorkflowParametersUpdate(BaseModel):
    parameters: list[dict[str, object]]
