"""FastAPI application factory and dependency composition root.

All concrete infrastructure is assembled here. Route modules receive services,
services receive repositories and integration clients, and inner layers never
import FastAPI. This keeps dependencies flowing in one direction.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes.conversations import create_conversation_router
from app.api.routes.generations import create_generation_router
from app.api.routes.providers import create_provider_router
from app.api.routes.status import create_status_router
from app.core.config import Settings
from app.core.interfaces import CodexClient
from app.core.secrets import SecretBox
from app.core.security import is_origin_allowed
from app.db.database import Database
from app.db.repositories import ConversationRepository
from app.services.codex_app_server import CodexAppServerClient
from app.services.conversation_service import ConversationService
from app.services.generation_service import GenerationService
from app.services.provider_service import ProviderService


def create_app(
    client: CodexClient | None = None,
    *,
    settings: Settings | None = None,
    database_path: Path | None = None,
) -> FastAPI:
    """Build an independently testable application with injectable dependencies."""

    app_settings = settings or Settings.from_env()
    codex_client = client or CodexAppServerClient(
        binary=app_settings.codex_binary,
        workspace=app_settings.codex_workspace,
        protocol_log=app_settings.protocol_log_path,
        protocol_logging_enabled=app_settings.protocol_logging_enabled,
    )
    database = Database(database_path or app_settings.database_path)
    repository = ConversationRepository(database)
    provider_service = ProviderService(database, SecretBox(app_settings.secret_key_path))
    conversation_service = ConversationService(repository, codex_client, provider_service)
    generation_service = GenerationService(repository, provider_service, app_settings.asset_dir)

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        # A startup failure leaves the API available in degraded mode so the UI
        # can display actionable connection status instead of a blank page.
        startup_error: str | None = None
        try:
            await codex_client.start()
        except Exception as exc:  # noqa: BLE001 - health endpoint exposes the failure
            startup_error = str(exc)
        api.state.startup_error = startup_error
        yield
        await codex_client.stop()
        database.close()

    api = FastAPI(title="造境 Codex Gateway", version="0.3.0", lifespan=lifespan)
    api.state.codex = codex_client
    api.state.conversation_service = conversation_service
    api.state.provider_service = provider_service
    api.state.generation_service = generation_service
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
        create_conversation_router(conversation_service, app_settings.allowed_origins)
    )
    api.include_router(create_provider_router(provider_service))
    api.include_router(create_generation_router(generation_service, repository))
    return api


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
