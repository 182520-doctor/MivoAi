"""HTTP endpoints for durable image and video generation tasks."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.exceptions import ProviderConfigurationError
from app.models.gateway import GenerationCreate
from app.services.generation_service import GenerationService


def create_generation_router(service: GenerationService, repository) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["generations"])

    @router.post("/generations")
    async def create_generation(payload: GenerationCreate):
        return await service.create(payload)

    @router.get("/generations/{task_id}")
    async def get_generation(task_id: str):
        return service.get(task_id)

    @router.get("/assets/{asset_id}")
    async def get_asset(asset_id: str):
        asset = repository.get_asset(asset_id)
        if not asset or not asset.get("local_path"):
            raise ProviderConfigurationError("素材不存在")
        return FileResponse(asset["local_path"], media_type=asset.get("mime_type"))

    return router
