"""HTTP routes for deterministic media preparation."""

from fastapi import APIRouter

from app.contexts.media_processing.application import MediaProcessingService
from app.contexts.media_processing.schemas import (
    AudioExtractionRequest,
    AudioNormalizeRequest,
    AudioTranscriptionRequest,
    SpeechSynthesisRequest,
    VideoUpscaleRequest,
)


def create_media_processing_router(
    service: MediaProcessingService,
) -> APIRouter:
    router = APIRouter(prefix="/api/media/processing", tags=["media-processing"])

    @router.post("/extract-audio")
    async def extract_audio(payload: AudioExtractionRequest):
        return service.extract_audio(payload.video_asset_id)

    @router.get("/tts/voices")
    async def speech_voices():
        return {"voices": service.speech_voices()}

    @router.post("/tts")
    async def synthesize_speech(payload: SpeechSynthesisRequest):
        return service.synthesize_speech(
            payload.text,
            voice_name=payload.voice_name,
            rate=payload.rate,
            filename=f"tts-{payload.voice_name}.wav",
        )

    @router.post("/normalize-audio")
    async def normalize_audio(payload: AudioNormalizeRequest):
        return service.normalize_audio(
            payload.audio_asset_id,
            target_lufs=payload.target_lufs,
            true_peak_db=payload.true_peak_db,
            loudness_range=payload.loudness_range,
        )

    @router.post("/transcribe-audio")
    async def transcribe_audio(payload: AudioTranscriptionRequest):
        return service.transcribe_audio(
            payload.audio_asset_id,
            language=payload.language,
        )

    @router.post("/upscale-video")
    async def upscale_video(payload: VideoUpscaleRequest):
        return service.upscale_video(
            payload.video_asset_id,
            aspect_ratio=payload.aspect_ratio,
        )

    return router
