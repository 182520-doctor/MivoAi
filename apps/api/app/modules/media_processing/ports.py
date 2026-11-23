"""Ports for deterministic local media processing."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class MediaArtifactPort(Protocol):
    def get(self, asset_id: str) -> dict[str, object]: ...

    def get_content(self, asset_id: str) -> tuple[str, str | None]: ...

    def import_local(
        self,
        *,
        source_path: Path,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str: ...


class AudioExtractionPort(Protocol):
    def extract_audio(self, source: Path, destination: Path) -> None: ...


class AudioNormalizationPort(Protocol):
    def normalize_audio(
        self,
        source: Path,
        destination: Path,
        *,
        target_lufs: float,
        true_peak_db: float,
        loudness_range: float,
    ) -> dict[str, object]: ...


class WhisperTranscriptionPort(Protocol):
    def transcribe(
        self,
        source: Path,
        destination: Path,
        *,
        language: str,
    ) -> list[dict[str, object]]: ...


class VideoCompositionPort(Protocol):
    def compose_videos(
        self,
        sources: list[Path],
        destination: Path,
        *,
        aspect_ratio: str,
        subtitle_path: Path | None = None,
        subtitle_style: dict[str, object] | None = None,
        audio_sources: list[Path | None] | None = None,
        transition: str = "none",
        transition_duration: float = 0.4,
        music_source: Path | None = None,
        music_volume_db: float = -18,
        ambience_source: Path | None = None,
        ambience_volume_db: float = -22,
        ducking: bool = True,
        sound_effects: list[dict[str, object]] | None = None,
    ) -> None: ...


class SpeechSynthesisPort(Protocol):
    def list_voices(self) -> list[dict[str, object]]: ...

    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        voice_name: str,
        rate: int,
    ) -> None: ...


class VideoUpscalePort(Protocol):
    def upscale_video(
        self,
        source: Path,
        destination: Path,
        *,
        width: int,
        height: int,
    ) -> None: ...
