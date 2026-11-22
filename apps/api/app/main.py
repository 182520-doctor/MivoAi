"""FastAPI application factory with bounded-context route registration."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.composition import build_container
from app.delivery.http.api import register_http_routes
from app.delivery.http.errors import register_exception_handlers
from app.modules.conversations.ports import CodexClient
from app.modules.drama.ports import (
    DramaProductionMediaPort,
    DramaTimelineRendererPort,
)
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
    register_http_routes(
        api,
        container,
        allowed_origins=app_settings.allowed_origins,
    )
    return api


app_settings = Settings.from_env()
app = create_app(settings=app_settings)


def _parse_listening_ports(output: str) -> set[int]:
    ports: set[int] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        if parts[-2].upper() not in {"LISTEN", "LISTENING", "侦听"}:
            continue
        address = parts[1] if parts[0] == "TCP" else parts[3]
        if ":" not in address:
            continue
        try:
            ports.add(int(address.rsplit(":", 1)[1]))
        except ValueError:
            continue
    return ports


def _listening_ports() -> set[int]:
    command = ["netstat", "-ano"] if os.name == "nt" else ["ss", "-lnt"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return _parse_listening_ports(result.stdout) if result.returncode == 0 else set()


def _ensure_port_is_available(port: int) -> None:
    if port in _listening_ports():
        raise SystemExit(
            f"Backend port {port} is already in use. Stop the old process first."
        )


if __name__ == "__main__":
    _ensure_port_is_available(app_settings.api_port)
    # Uvicorn's Windows reload supervisor does not start a worker under pythonw.
    reload_enabled = Path(sys.executable).name.lower() != "pythonw.exe"
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=app_settings.api_port,
        reload=reload_enabled,
        app_dir=str(Path(__file__).resolve().parent.parent),
    )
