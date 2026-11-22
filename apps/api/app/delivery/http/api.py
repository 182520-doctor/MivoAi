"""Single composition point for the public HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.delivery.http.routes.assets import create_asset_router
from app.delivery.http.routes.conversations import create_conversation_router
from app.delivery.http.routes.creative_projects import (
    create_creative_project_router,
)
from app.delivery.http.routes.drama import create_drama_router
from app.delivery.http.routes.media_generation import create_generation_router
from app.delivery.http.routes.media_processing import (
    create_media_processing_router,
)
from app.delivery.http.routes.providers import create_provider_router
from app.delivery.http.routes.system import create_status_router
from app.delivery.http.routes.workflows import create_workflow_router

if TYPE_CHECKING:
    from app.composition import ApplicationContainer


def register_http_routes(
    api: FastAPI,
    container: ApplicationContainer,
    *,
    allowed_origins: tuple[str, ...],
) -> None:
    """Register every public HTTP route from one discoverable location."""

    api.include_router(create_status_router(container.codex_client))
    api.include_router(
        create_conversation_router(
            container.conversation_service,
            allowed_origins,
        )
    )
    api.include_router(
        create_creative_project_router(container.creative_project_service)
    )
    api.include_router(create_provider_router(container.provider_service))
    api.include_router(
        create_generation_router(container.generation_service)
    )
    api.include_router(
        create_media_processing_router(container.media_processing_service)
    )
    api.include_router(create_asset_router(container.asset_service))
    api.include_router(create_workflow_router(container.workflow_service))
    api.include_router(create_drama_router(container.drama_service))
