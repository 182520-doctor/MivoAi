"""HTTP endpoints for durable image and video generation tasks."""

from fastapi import APIRouter

from app.contexts.media_generation.application import GenerationService
from app.contexts.media_generation.schemas import (
    GenerationCreate,
    GenerationRetryBatch,
)


def create_generation_router(service: GenerationService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["generations"])

    @router.post("/generations")
    async def create_generation(payload: GenerationCreate):
        return await service.create(payload.to_command())

    @router.get("/generations")
    async def list_generations(
        limit: int = 100,
        taskType: str | None = None,
        status: str | None = None,
    ):
        return service.list(
            limit=limit,
            task_type=taskType,
            status=status,
        )

    @router.get("/generations/{task_id}")
    async def get_generation(task_id: str):
        return service.get(task_id)

    @router.post("/generations/{task_id}/retry")
    async def retry_generation(task_id: str):
        return await service.retry(task_id)

    @router.post("/generations/retry-batch")
    async def retry_generation_batch(payload: GenerationRetryBatch):
        return await service.retry_many(payload.task_ids)

    return router
