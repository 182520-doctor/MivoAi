"""Composition root for bounded-context application services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adapters.codex.app_server import (
    CodexAppServerClient,
)
from app.adapters.comfyui.client import ComfyUIClient
from app.adapters.media.downloader import HttpAssetFetcher
from app.adapters.media.ffmpeg import (
    FFmpegAudioExtractor,
    FFmpegAudioNormalizer,
    FFmpegVideoComposer,
    FFmpegVideoUpscaler,
    FFmpegWhisperTranscriber,
)
from app.adapters.media.production_media import (
    GenerationProductionMediaAdapter,
)
from app.adapters.media.speech import (
    WindowsSapiSpeechSynthesizer,
)
from app.adapters.persistence.database import Database
from app.adapters.persistence.sqlite.assets import AssetRepository
from app.adapters.persistence.sqlite.conversations import ConversationRepository
from app.adapters.persistence.sqlite.creative_projects import (
    CreativeProjectRepository,
)
from app.adapters.persistence.sqlite.drama import DramaProjectRepository
from app.adapters.persistence.sqlite.media_generation import (
    GenerationTaskRepository,
)
from app.adapters.persistence.sqlite.providers import ProviderRepository
from app.adapters.persistence.sqlite.workflows import (
    ComfyWorkflowRepository,
)
from app.adapters.providers.media_gateway import MediaProviderGateway
from app.adapters.providers.volcengine import VolcengineChatClient
from app.adapters.workspaces.conversations import ConversationWorkspaceManager
from app.adapters.workspaces.drama import DramaWorkspaceManager
from app.delivery.agent.media_tools import (
    AgentMediaToolService,
    media_dynamic_tool_specs,
)
from app.modules.assets import AssetService
from app.modules.conversations import ConversationService
from app.modules.conversations.ports import CodexClient
from app.modules.creative_projects import CreativeProjectService
from app.modules.creative_projects.domain import CreativeProjectQualityPolicy
from app.modules.drama import DramaProjectService
from app.modules.drama.ports import (
    DramaProductionMediaPort,
    DramaTimelineRendererPort,
)
from app.modules.media_generation import GenerationService
from app.modules.media_processing import MediaProcessingService
from app.modules.providers import ProviderService
from app.modules.workflows import WorkflowService
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
        comfyui_url=settings.comfyui_url,
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
        comfyui_url=settings.comfyui_url,
    )
    creative_quality_policy = CreativeProjectQualityPolicy()
    conversation_service = ConversationService(
        conversation_repository,
        client,
        provider_service,
        generation_service,
        workspace_manager,
        creative_projects=creative_repository,
        quality_gate=creative_quality_policy,
    )
    creative_project_service = CreativeProjectService(
        creative_repository,
        settings.creative_workspace_dir,
        quality_policy=creative_quality_policy,
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
