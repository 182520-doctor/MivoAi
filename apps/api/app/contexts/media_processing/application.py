"""Use cases for local media preparation."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.contexts.media_processing.ports import (
    AudioExtractionPort,
    AudioNormalizationPort,
    MediaArtifactPort,
    SpeechSynthesisPort,
    VideoCompositionPort,
    VideoUpscalePort,
    WhisperTranscriptionPort,
)
from app.shared.errors import ProviderConfigurationError


class MediaProcessingService:
    def __init__(
        self,
        artifacts: MediaArtifactPort,
        audio_extractor: AudioExtractionPort,
        video_composer: VideoCompositionPort,
        speech_synthesizer: SpeechSynthesisPort,
        video_upscaler: VideoUpscalePort,
        work_dir: Path,
        audio_normalizer: AudioNormalizationPort | None = None,
        transcriber: WhisperTranscriptionPort | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._audio_extractor = audio_extractor
        self._video_composer = video_composer
        self._speech_synthesizer = speech_synthesizer
        self._video_upscaler = video_upscaler
        self._work_dir = work_dir
        self._audio_normalizer = audio_normalizer
        self._transcriber = transcriber

    def extract_audio(self, video_asset_id: str) -> dict[str, object]:
        video = self._artifacts.get(video_asset_id)
        if video.get("type") != "video":
            raise ProviderConfigurationError("只有视频素材可以提取音频")
        source_path, _ = self._artifacts.get_content(video_asset_id)
        destination = self._work_dir / f"{uuid.uuid4()}.m4a"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._audio_extractor.extract_audio(
                Path(source_path),
                destination,
            )
            filename = f"{video_asset_id}-audio.m4a"
            asset_id = self._artifacts.import_local(
                source_path=destination,
                asset_type="audio",
                filename=filename,
                metadata={
                    "operation": "extract_audio",
                    "sourceAssetId": video_asset_id,
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
        return {
            "assetId": asset_id,
            "sourceAssetId": video_asset_id,
            "type": "audio",
            "url": f"/api/assets/{asset_id}",
        }

    def render_timeline(
        self,
        video_asset_ids: list[str],
        *,
        aspect_ratio: str,
        filename: str,
        subtitle_cues: list[dict[str, object]] | None = None,
        subtitle_style: dict[str, object] | None = None,
        audio_asset_ids: list[str | None] | None = None,
        transition: str = "none",
        transition_duration: float = 0.4,
        music_asset_id: str | None = None,
        music_volume_db: float = -18,
        ambience_asset_id: str | None = None,
        ambience_volume_db: float = -22,
        ducking: bool = True,
        sound_effects: list[dict[str, object]] | None = None,
    ) -> str:
        if not video_asset_ids:
            raise ProviderConfigurationError("整集合成至少需要一个镜头视频")
        sources: list[Path] = []
        for asset_id in video_asset_ids:
            asset = self._artifacts.get(asset_id)
            if asset.get("type") != "video":
                raise ProviderConfigurationError("整集合成只接受视频素材")
            source_path, _ = self._artifacts.get_content(asset_id)
            sources.append(Path(source_path))
        normalized_audio_ids = list(audio_asset_ids or [])[: len(video_asset_ids)]
        normalized_audio_ids.extend(
            [None] * (len(video_asset_ids) - len(normalized_audio_ids))
        )
        audio_sources: list[Path | None] = []
        for index, audio_asset_id in enumerate(normalized_audio_ids):
            if not audio_asset_id:
                audio_sources.append(None)
                continue
            audio = self._artifacts.get(audio_asset_id)
            if audio.get("type") != "audio":
                raise ProviderConfigurationError(
                    f"第 {index + 1} 个镜头的配音素材不是音频"
                )
            audio_path, _ = self._artifacts.get_content(audio_asset_id)
            audio_sources.append(Path(audio_path))
        music_source = self._audio_asset_path(music_asset_id)
        ambience_source = self._audio_asset_path(ambience_asset_id)
        resolved_effects: list[dict[str, object]] = []
        for effect in sound_effects or []:
            asset_id = str(effect.get("assetId") or "")
            source = self._audio_asset_path(asset_id)
            if not source:
                continue
            resolved_effects.append(
                {
                    "source": source,
                    "startSeconds": float(
                        effect.get("startSeconds") or 0
                    ),
                    "durationSeconds": float(
                        effect.get("durationSeconds") or 0
                    ),
                    "volumeDb": float(effect.get("volumeDb") or 0),
                }
            )
        destination = self._work_dir / f"{uuid.uuid4()}.mp4"
        subtitle_path = (
            self._work_dir / f"{uuid.uuid4()}.srt"
            if subtitle_cues
            else None
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if subtitle_path:
                subtitle_path.write_text(
                    _srt_document(subtitle_cues or []),
                    encoding="utf-8",
                )
            self._video_composer.compose_videos(
                sources,
                destination,
                aspect_ratio=aspect_ratio,
                subtitle_path=subtitle_path,
                subtitle_style=subtitle_style,
                audio_sources=audio_sources,
                transition=transition,
                transition_duration=transition_duration,
                music_source=music_source,
                music_volume_db=music_volume_db,
                ambience_source=ambience_source,
                ambience_volume_db=ambience_volume_db,
                ducking=ducking,
                sound_effects=resolved_effects,
            )
            return self._artifacts.import_local(
                source_path=destination,
                asset_type="video",
                filename=filename,
                metadata={
                    "operation": "render_timeline",
                    "sourceAssetIds": video_asset_ids,
                    "aspectRatio": aspect_ratio,
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
            if subtitle_path:
                subtitle_path.unlink(missing_ok=True)

    def speech_voices(self) -> list[dict[str, object]]:
        return self._speech_synthesizer.list_voices()

    def normalize_audio(
        self,
        audio_asset_id: str,
        *,
        target_lufs: float = -16,
        true_peak_db: float = -1.5,
        loudness_range: float = 11,
    ) -> dict[str, object]:
        if not self._audio_normalizer:
            raise ProviderConfigurationError("音频响度标准化组件尚未配置")
        audio = self._artifacts.get(audio_asset_id)
        if audio.get("type") != "audio":
            raise ProviderConfigurationError("响度标准化只接受音频素材")
        source_path, _ = self._artifacts.get_content(audio_asset_id)
        destination = self._work_dir / f"{uuid.uuid4()}.m4a"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            measurements = self._audio_normalizer.normalize_audio(
                Path(source_path),
                destination,
                target_lufs=target_lufs,
                true_peak_db=true_peak_db,
                loudness_range=loudness_range,
            )
            filename = f"{audio_asset_id}-normalized.m4a"
            asset_id = self._artifacts.import_local(
                source_path=destination,
                asset_type="audio",
                filename=filename,
                metadata={
                    "operation": "normalize_audio",
                    "sourceAssetId": audio_asset_id,
                    "targetLufs": target_lufs,
                    "truePeakDb": true_peak_db,
                    "loudnessRange": loudness_range,
                    "measurements": measurements,
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
        return {
            "assetId": asset_id,
            "sourceAssetId": audio_asset_id,
            "type": "audio",
            "url": f"/api/assets/{asset_id}",
            "targetLufs": target_lufs,
        }

    def transcribe_audio(
        self,
        audio_asset_id: str,
        *,
        language: str = "auto",
    ) -> dict[str, object]:
        if not self._transcriber:
            raise ProviderConfigurationError("语音转写组件尚未配置")
        audio = self._artifacts.get(audio_asset_id)
        if audio.get("type") != "audio":
            raise ProviderConfigurationError("语音转写只接受音频素材")
        source_path, _ = self._artifacts.get_content(audio_asset_id)
        destination = self._work_dir / f"{uuid.uuid4()}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            cues = self._transcriber.transcribe(
                Path(source_path),
                destination,
                language=language,
            )
            destination.write_text(
                json.dumps(cues, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            filename = f"{audio_asset_id}-transcript.json"
            asset_id = self._artifacts.import_local(
                source_path=destination,
                asset_type="file",
                filename=filename,
                metadata={
                    "operation": "transcribe_audio",
                    "sourceAssetId": audio_asset_id,
                    "language": language,
                    "cueCount": len(cues),
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
        return {
            "assetId": asset_id,
            "sourceAssetId": audio_asset_id,
            "type": "file",
            "language": language,
            "cues": cues,
            "url": f"/api/assets/{asset_id}",
        }

    def synthesize_speech(
        self,
        text: str,
        *,
        voice_name: str,
        rate: int,
        filename: str,
    ) -> dict[str, object]:
        destination = self._work_dir / f"{uuid.uuid4()}.wav"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._speech_synthesizer.synthesize(
                text,
                destination,
                voice_name=voice_name,
                rate=rate,
            )
            asset_id = self._artifacts.import_local(
                source_path=destination,
                asset_type="audio",
                filename=filename,
                metadata={
                    "operation": "tts",
                    "voiceName": voice_name,
                    "rate": rate,
                    "text": text,
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
        return {
            "assetId": asset_id,
            "type": "audio",
            "url": f"/api/assets/{asset_id}",
        }

    def _audio_asset_path(self, asset_id: str | None) -> Path | None:
        if not asset_id:
            return None
        asset = self._artifacts.get(asset_id)
        if asset.get("type") != "audio":
            raise ProviderConfigurationError("背景轨道必须是音频素材")
        path, _ = self._artifacts.get_content(asset_id)
        return Path(path)

    def upscale_video(
        self,
        video_asset_id: str,
        *,
        aspect_ratio: str,
    ) -> dict[str, object]:
        video = self._artifacts.get(video_asset_id)
        if video.get("type") != "video":
            raise ProviderConfigurationError("视频超分只接受视频素材")
        source_path, _ = self._artifacts.get_content(video_asset_id)
        width, height = _composition_dimensions(aspect_ratio)
        destination = self._work_dir / f"{uuid.uuid4()}.mp4"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._video_upscaler.upscale_video(
                Path(source_path),
                destination,
                width=width,
                height=height,
            )
            filename = f"{video_asset_id}-upscaled.mp4"
            asset_id = self._artifacts.import_local(
                source_path=destination,
                asset_type="video",
                filename=filename,
                metadata={
                    "operation": "video_upscale",
                    "sourceAssetId": video_asset_id,
                    "width": width,
                    "height": height,
                    "aspectRatio": aspect_ratio,
                    "originalFilename": filename,
                },
            )
        finally:
            destination.unlink(missing_ok=True)
        return {
            "assetId": asset_id,
            "sourceAssetId": video_asset_id,
            "type": "video",
            "url": f"/api/assets/{asset_id}",
        }


def _srt_document(cues: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        start = max(0.0, float(cue.get("startSeconds") or 0))
        end = max(start + 0.1, float(cue.get("endSeconds") or start + 1))
        blocks.append(
            f"{index}\n"
            f"{_srt_time(start)} --> {_srt_time(end)}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _composition_dimensions(aspect_ratio: str) -> tuple[int, int]:
    return {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }.get(aspect_ratio, (1920, 1080))
