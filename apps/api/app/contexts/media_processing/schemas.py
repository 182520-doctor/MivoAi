"""HTTP schemas for media processing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioExtractionRequest(BaseModel):
    video_asset_id: str = Field(alias="videoAssetId", min_length=1, max_length=80)

    model_config = {"populate_by_name": True}


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_name: str = Field(
        default="Microsoft Huihui Desktop",
        alias="voiceName",
        max_length=160,
    )
    rate: int = Field(default=0, ge=-10, le=10)

    model_config = {"populate_by_name": True}


class AudioNormalizeRequest(BaseModel):
    audio_asset_id: str = Field(
        alias="audioAssetId",
        min_length=1,
        max_length=80,
    )
    target_lufs: float = Field(
        default=-16,
        alias="targetLufs",
        ge=-24,
        le=-9,
    )
    true_peak_db: float = Field(
        default=-1.5,
        alias="truePeakDb",
        ge=-6,
        le=-0.1,
    )
    loudness_range: float = Field(
        default=11,
        alias="loudnessRange",
        ge=1,
        le=30,
    )

    model_config = {"populate_by_name": True}


class AudioTranscriptionRequest(BaseModel):
    audio_asset_id: str = Field(
        alias="audioAssetId",
        min_length=1,
        max_length=80,
    )
    language: str = Field(default="auto", max_length=12)

    model_config = {"populate_by_name": True}


class VideoUpscaleRequest(BaseModel):
    video_asset_id: str = Field(
        alias="videoAssetId",
        min_length=1,
        max_length=80,
    )
    aspect_ratio: str = Field(
        default="9:16",
        alias="aspectRatio",
        max_length=20,
    )

    model_config = {"populate_by_name": True}
