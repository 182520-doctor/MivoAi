import json
from pathlib import Path

from app.adapters.persistence.database import Database
from app.adapters.persistence.sqlite.media_generation import (
    GenerationTaskRepository,
)
from app.modules.media_processing.application import MediaProcessingService


class FakeArtifacts:
    def __init__(self, source: Path) -> None:
        self._source = source
        self.imported: list[dict[str, object]] = []

    def get(self, asset_id: str) -> dict[str, object]:
        return {
            "id": asset_id,
            "type": "audio" if asset_id.startswith("audio") else "video",
        }

    def get_content(self, asset_id: str) -> tuple[str, str | None]:
        return (
            str(self._source),
            "audio/wav" if asset_id.startswith("audio") else "video/mp4",
        )

    def import_local(
        self,
        *,
        source_path: Path,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        self.imported.append(
            {
                "sourcePath": source_path,
                "assetType": asset_type,
                "filename": filename,
                "metadata": metadata,
                "content": (
                    source_path.read_text(encoding="utf-8")
                    if source_path.suffix == ".json"
                    else None
                ),
            }
        )
        return "audio-1"


class FakeAudioExtractor:
    def extract_audio(self, source: Path, destination: Path) -> None:
        assert source.name == "clip.mp4"
        destination.write_bytes(b"audio")


class FakeAudioNormalizer:
    def normalize_audio(
        self,
        source: Path,
        destination: Path,
        *,
        target_lufs: float,
        true_peak_db: float,
        loudness_range: float,
    ) -> dict[str, object]:
        assert source.name == "clip.mp4"
        assert target_lufs == -16
        assert true_peak_db == -1.5
        assert loudness_range == 11
        destination.write_bytes(b"normalized-audio")
        return {
            "input_i": -23.4,
            "input_tp": -6.2,
            "input_lra": 4.1,
            "input_thresh": -34.0,
            "target_offset": 7.4,
        }


class FakeTranscriber:
    def transcribe(
        self,
        source: Path,
        destination: Path,
        *,
        language: str,
    ) -> list[dict[str, object]]:
        assert source.name == "clip.mp4"
        assert language == "zh"
        destination.write_text(
            '{"start":0,"end":1200,"text":"测试字幕"}\n',
            encoding="utf-8",
        )
        return [
            {
                "startSeconds": 0,
                "endSeconds": 1.2,
                "text": "测试字幕",
            }
        ]


class FakeVideoComposer:
    def __init__(self) -> None:
        self.subtitle_path: Path | None = None

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
    ) -> None:
        assert len(sources) == 2
        assert aspect_ratio == "9:16"
        self.subtitle_path = subtitle_path
        if subtitle_path:
            assert "00:00:00,000 --> 00:00:02,000" in (
                subtitle_path.read_text(encoding="utf-8")
            )
        destination.write_bytes(b"video")


class FakeSpeechSynthesizer:
    def list_voices(self) -> list[dict[str, object]]:
        return [{"name": "Huihui", "culture": "zh-CN"}]

    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        voice_name: str,
        rate: int,
    ) -> None:
        assert text == "你好"
        assert voice_name == "Huihui"
        assert rate == 0
        destination.write_bytes(b"wav")


class FakeVideoUpscaler:
    def upscale_video(
        self,
        source: Path,
        destination: Path,
        *,
        width: int,
        height: int,
    ) -> None:
        assert source.name == "clip.mp4"
        assert (width, height) == (1080, 1920)
        destination.write_bytes(b"upscaled-video")


def test_extract_audio_imports_artifact_and_removes_work_file(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    artifacts = FakeArtifacts(source)
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        FakeVideoComposer(),
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
    )

    result = service.extract_audio("video-1")

    assert result == {
        "assetId": "audio-1",
        "sourceAssetId": "video-1",
        "type": "audio",
        "url": "/api/assets/audio-1",
    }
    imported = artifacts.imported[0]
    assert imported["assetType"] == "audio"
    assert imported["metadata"] == {
        "operation": "extract_audio",
        "sourceAssetId": "video-1",
        "originalFilename": "video-1-audio.m4a",
    }
    assert not Path(imported["sourcePath"]).exists()


def test_render_timeline_imports_composed_video(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    artifacts = FakeArtifacts(source)
    composer = FakeVideoComposer()
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        composer,
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
    )

    asset_id = service.render_timeline(
        ["video-1", "video-2"],
        aspect_ratio="9:16",
        filename="episode-1.mp4",
        subtitle_cues=[
            {
                "startSeconds": 0,
                "endSeconds": 2,
                "text": "中文字幕测试",
            }
        ],
    )

    assert asset_id == "audio-1"
    imported = artifacts.imported[-1]
    assert imported["assetType"] == "video"
    assert imported["metadata"] == {
        "operation": "render_timeline",
        "sourceAssetIds": ["video-1", "video-2"],
        "aspectRatio": "9:16",
        "originalFilename": "episode-1.mp4",
    }
    assert not Path(imported["sourcePath"]).exists()
    assert composer.subtitle_path is not None
    assert not composer.subtitle_path.exists()


def test_synthesize_speech_imports_audio(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    artifacts = FakeArtifacts(source)
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        FakeVideoComposer(),
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
    )

    result = service.synthesize_speech(
        "你好",
        voice_name="Huihui",
        rate=0,
        filename="shot-1-voice.wav",
    )

    assert result == {
        "assetId": "audio-1",
        "type": "audio",
        "url": "/api/assets/audio-1",
    }
    imported = artifacts.imported[-1]
    assert imported["assetType"] == "audio"
    assert imported["metadata"] == {
        "operation": "tts",
        "voiceName": "Huihui",
        "rate": 0,
        "text": "你好",
        "originalFilename": "shot-1-voice.wav",
    }


def test_normalize_audio_imports_leveled_artifact(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"audio")
    artifacts = FakeArtifacts(source)
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        FakeVideoComposer(),
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
        audio_normalizer=FakeAudioNormalizer(),
    )

    result = service.normalize_audio("audio-1")

    assert result == {
        "assetId": "audio-1",
        "sourceAssetId": "audio-1",
        "type": "audio",
        "url": "/api/assets/audio-1",
        "targetLufs": -16,
    }
    imported = artifacts.imported[-1]
    assert imported["assetType"] == "audio"
    assert imported["metadata"]["operation"] == "normalize_audio"
    assert imported["metadata"]["targetLufs"] == -16
    assert imported["metadata"]["measurements"]["input_i"] == -23.4


def test_transcribe_audio_imports_timeline_artifact(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"audio")
    artifacts = FakeArtifacts(source)
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        FakeVideoComposer(),
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
        transcriber=FakeTranscriber(),
    )

    result = service.transcribe_audio("audio-1", language="zh")

    assert result == {
        "assetId": "audio-1",
        "sourceAssetId": "audio-1",
        "type": "file",
        "language": "zh",
        "cues": [
            {
                "startSeconds": 0,
                "endSeconds": 1.2,
                "text": "测试字幕",
            }
        ],
        "url": "/api/assets/audio-1",
    }
    imported = artifacts.imported[-1]
    assert imported["assetType"] == "file"
    assert imported["metadata"]["operation"] == "transcribe_audio"
    assert imported["metadata"]["cueCount"] == 1
    assert json.loads(imported["content"]) == result["cues"]


def test_upscale_video_imports_video(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    artifacts = FakeArtifacts(source)
    service = MediaProcessingService(
        artifacts,
        FakeAudioExtractor(),
        FakeVideoComposer(),
        FakeSpeechSynthesizer(),
        FakeVideoUpscaler(),
        tmp_path / "processing",
    )

    result = service.upscale_video("video-1", aspect_ratio="9:16")

    assert result == {
        "assetId": "audio-1",
        "sourceAssetId": "video-1",
        "type": "video",
        "url": "/api/assets/audio-1",
    }
    imported = artifacts.imported[-1]
    assert imported["assetType"] == "video"
    assert imported["metadata"] == {
        "operation": "video_upscale",
        "sourceAssetId": "video-1",
        "width": 1080,
        "height": 1920,
        "aspectRatio": "9:16",
        "originalFilename": "video-1-upscaled.mp4",
    }


def test_nonterminal_task_clears_completed_timestamp(tmp_path) -> None:
    database = Database(tmp_path / "tasks.db")
    repository = GenerationTaskRepository(database)
    task_id = repository.create(
        session_id=None,
        turn_id=None,
        user_id="local-user",
        provider_id="comfyui",
        model_id="comfy-wan-video",
        prompt="test",
        original_request={},
        normalized_request={},
        client_request_id="request-1",
        task_type="video_generation",
        status="queued",
    )
    repository.update_status(task_id, status="running", completed=True)
    assert repository.get(task_id)["completed_at"] is not None

    repository.update_status(task_id, status="running", completed=False)
    assert repository.get(task_id)["completed_at"] is None

    repository.update_status(task_id, status="succeeded", completed=True)
    assert repository.get(task_id)["completed_at"] is not None
    database.close()
