"""FastAPI application factory with bounded-context route registration."""

from __future__ import annotations

import socket
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.creative_projects import create_creative_project_router
from app.composition import build_container
from app.contexts.assets.routes import create_asset_router
from app.contexts.conversations.ports import CodexClient
from app.contexts.conversations.routes import create_conversation_router
from app.contexts.drama.ports import (
    DramaProductionMediaPort,
    DramaTimelineRendererPort,
)
from app.contexts.drama.routes import create_drama_router
from app.contexts.media_generation.routes import create_generation_router
from app.contexts.media_processing.routes import create_media_processing_router
from app.contexts.providers.routes import create_provider_router
from app.contexts.system.routes import create_status_router
from app.contexts.workflows.routes import create_workflow_router
from app.interfaces.errors import register_exception_handlers
from app.shared.config import Settings
from app.shared.security import is_origin_allowed


def create_app(
    client: CodexClient | None = None,
    *,
    settings: Settings | None = None,
    database_path: Path | None = None,
    timeline_renderer: DramaTimelineRendererPort | None = None,
    production_media: DramaProductionMediaPort | None = None,
) -> FastAPI:
    """Build an independently testable application with injectable dependencies."""

    app_settings = settings or Settings.from_env()
    container = build_container(
        app_settings,
        codex_client=client,
        database_path=database_path,
        timeline_renderer=timeline_renderer,
        production_media=production_media,
    )
    codex_client = container.codex_client
    conversation_service = container.conversation_service
    provider_service = container.provider_service
    generation_service = container.generation_service
    media_processing_service = container.media_processing_service
    asset_service = container.asset_service
    workflow_service = container.workflow_service
    drama_service = container.drama_service
    creative_project_service = container.creative_project_service

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        # A startup failure leaves the API available in degraded mode so the UI
        # can display actionable connection status instead of a blank page.
        api.state.recovered_conversation_turns = (
            conversation_service.recover_interrupted()
        )
        startup_error: str | None = None
        try:
            await codex_client.start()
        except Exception as exc:  # noqa: BLE001 - health endpoint exposes the failure
            startup_error = str(exc)
        api.state.startup_error = startup_error
        api.state.resumed_generation_tasks = (
            await generation_service.resume_interrupted()
        )
        api.state.resumed_drama_runs = (
            await drama_service.resume_production_runs()
        )
        yield
        await codex_client.stop()
        container.database.close()

    api = FastAPI(title="造境 Codex Gateway", version="0.4.0", lifespan=lifespan)
    api.state.codex = codex_client
    api.state.conversation_service = conversation_service
    api.state.provider_service = provider_service
    api.state.generation_service = generation_service
    api.state.media_processing_service = media_processing_service
    api.state.asset_service = asset_service
    api.state.workflow_service = workflow_service
    api.state.drama_service = drama_service
    api.state.creative_project_service = creative_project_service
    api.state.container = container
    api.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(app_settings.allowed_hosts)
    )

    @api.middleware("http")
    async def enforce_browser_origin(request: Request, call_next):
        if not is_origin_allowed(
            request.headers.get("origin"), app_settings.allowed_origins
        ):
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)

    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(api)
    api.include_router(create_status_router(codex_client))
    api.include_router(
        create_conversation_router(
            conversation_service,
            app_settings.allowed_origins,
        )
    )
    api.include_router(
        create_creative_project_router(creative_project_service)
    )
    api.include_router(create_provider_router(provider_service))
    api.include_router(create_generation_router(generation_service))
    api.include_router(create_media_processing_router(media_processing_service))
    api.include_router(create_asset_router(asset_service))
    api.include_router(create_workflow_router(workflow_service))
    api.include_router(create_drama_router(drama_service))
    return api


app_settings = Settings.from_env()
app = create_app(settings=app_settings)


def _available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise RuntimeError(f"No free backend port found near {preferred}")


if __name__ == "__main__":
    port = _available_port(app_settings.api_port)
    if port != app_settings.api_port:
        print(
            f"Port {app_settings.api_port} is in use; using backend port {port}",
            flush=True,
        )
    uvicorn.run(app, host="127.0.0.1", port=port, reload=True)
