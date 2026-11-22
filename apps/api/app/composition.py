"""Composition root for bounded-context application services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.contexts.assets.application import AssetService
from app.contexts.assets.infrastructure.downloader import HttpAssetFetcher
from app.contexts.assets.repository import AssetRepository
from app.contexts.conversations.application import ConversationService
from app.contexts.conversations.infrastructure.codex_app_server import (
    CodexAppServerClient,
)
from app.contexts.conversations.infrastructure.repository import ConversationRepository
from app.contexts.conversations.ports import CodexClient
from app.contexts.conversations.workspace import ConversationWorkspaceManager
from app.contexts.drama.application import DramaProjectService
from app.contexts.drama.infrastructure.production_media import (
    GenerationProductionMediaAdapter,
)
from app.contexts.drama.ports import (
    DramaProductionMediaPort,
    DramaTimelineRendererPort,
)
from app.contexts.drama.repository import DramaProjectRepository
from app.contexts.drama.workspace import DramaWorkspaceManager
from app.contexts.media_generation.application import GenerationService
from app.contexts.media_generation.repository import GenerationTaskRepository
from app.contexts.media_processing.application import MediaProcessingService
from app.contexts.media_processing.infrastructure.ffmpeg import (
    FFmpegAudioExtractor,
    FFmpegAudioNormalizer,
    FFmpegVideoComposer,
    FFmpegVideoUpscaler,
    FFmpegWhisperTranscriber,
)
from app.contexts.media_processing.infrastructure.windows_speech import (
    WindowsSapiSpeechSynthesizer,
)
from app.contexts.providers.application import ProviderService
from app.contexts.providers.infrastructure.comfyui import ComfyUIClient
from app.contexts.providers.infrastructure.media_gateway import MediaProviderGateway
from app.contexts.providers.infrastructure.volcengine import VolcengineChatClient
from app.contexts.providers.repository import ProviderRepository
from app.contexts.workflows.application import WorkflowService
from app.contexts.workflows.repository import ComfyWorkflowRepository
from app.db.repositories import CreativeProjectRepository
from app.infrastructure.persistence.database import Database
from app.interfaces.agent_media_tools import (
    AgentMediaToolService,
    media_dynamic_tool_specs,
)
from app.services.creative_project_service import CreativeProjectService
from app.services.quality_gate_service import QualityGateService
from app.shared.config import Settings
from app.shared.secrets import SecretBox


@dataclass(slots=True)
class ApplicationContainer:
    """Concrete dependencies assembled once at application startup."""

    settings: Settings
    codex_client: CodexClient
    database: Database
    conversation_service: ConversationService
    provider_service: ProviderService
    generation_service: GenerationService
    media_processing_service: MediaProcessingService
    asset_service: AssetService
    workflow_service: WorkflowService
    drama_service: DramaProjectService
    creative_project_service: CreativeProjectService


def build_container(
    settings: Settings,
    *,
    codex_client: CodexClient | None = None,
    database_path: Path | None = None,
    timeline_renderer: DramaTimelineRendererPort | None = None,
    production_media: DramaProductionMediaPort | None = None,
) -> ApplicationContainer:
    """Wire ports to adapters without leaking infrastructure into routes."""

    client: CodexClient | None = codex_client
    database = Database(database_path or settings.database_path)

    conversation_repository = ConversationRepository(database)
    creative_repository = CreativeProjectRepository(database)
    provider_repository = ProviderRepository(database)
    generation_repository = GenerationTaskRepository(database)
    asset_repository = AssetRepository(database)
    workflow_repository = ComfyWorkflowRepository(database)
    workflow_repository.normalize_standard_capabilities()
    drama_repository = DramaProjectRepository(database)

    provider_service = ProviderService(
        provider_repository,
        SecretBox(settings.secret_key_path),
        VolcengineChatClient(),
        lambda: client.status() if client else {},
    )
    asset_service = AssetService(asset_repository, settings.asset_dir, HttpAssetFetcher())
    comfyui_client = ComfyUIClient()
    generation_service = GenerationService(
        generation_repository,
        provider_service,
        asset_service,
        MediaProviderGateway(comfyui_client=comfyui_client),
    )
    media_processing_service = MediaProcessingService(
        asset_service,
        FFmpegAudioExtractor(),
        FFmpegVideoComposer(),
        WindowsSapiSpeechSynthesizer(
            settings.project_root / "scripts/tts_windows.ps1"
        ),
        FFmpegVideoUpscaler(),
        settings.asset_dir / "processing",
        audio_normalizer=FFmpegAudioNormalizer(),
        transcriber=FFmpegWhisperTranscriber(),
    )
    workspace_manager = ConversationWorkspaceManager(settings.codex_workspace)
    workspace_manager.initialize()
    drama_service = DramaProjectService(
        drama_repository,
        DramaWorkspaceManager(settings.drama_workspace),
        timeline_renderer or media_processing_service,
        asset_service,
        production_media=(
            production_media
            or GenerationProductionMediaAdapter(generation_service)
        ),
    )
    media_tools = AgentMediaToolService(
        provider_service,
        generation_service,
        asset_service,
        workspace_manager.shared_root,
        media_processing=media_processing_service,
        drama=drama_service,
    )
    if client is None:
        client = CodexAppServerClient(
            binary=settings.codex_binary,
            workspace=settings.codex_workspace,
            protocol_log=settings.protocol_log_path,
            protocol_logging_enabled=settings.protocol_logging_enabled,
            dynamic_tools=media_dynamic_tool_specs(),
            dynamic_tool_handler=media_tools.handle,
        )
    workflow_service = WorkflowService(
        workflow_repository,
        comfyui_client,
        asset_service,
    )
    conversation_service = ConversationService(
        conversation_repository,
        client,
        provider_service,
        generation_service,
        workspace_manager,
        creative_projects=creative_repository,
        quality_gate=QualityGateService(),
    )
    creative_project_service = CreativeProjectService(
        creative_repository,
        settings.creative_workspace_dir,
    )
    return ApplicationContainer(
        settings=settings,
        codex_client=client,
        database=database,
        conversation_service=conversation_service,
        provider_service=provider_service,
        generation_service=generation_service,
        media_processing_service=media_processing_service,
        asset_service=asset_service,
        workflow_service=workflow_service,
        drama_service=drama_service,
        creative_project_service=creative_project_service,
    )
