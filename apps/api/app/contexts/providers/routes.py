"""HTTP routes for the model catalog and local provider settings."""

from fastapi import APIRouter

from app.contexts.providers.application import ProviderService
from app.contexts.providers.schemas import (
    CredentialUpsert,
    ModelTestRequest,
    PreferenceUpdate,
)


def create_provider_router(service: ProviderService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["providers"])

    @router.get("/models")
    async def list_models():
        return service.list_models()

    @router.get("/preferences")
    async def get_preferences():
        return service.get_preferences()

    @router.put("/preferences")
    async def update_preferences(payload: PreferenceUpdate):
        return service.update_preferences(payload.to_command())

    @router.put("/providers/{provider_id}/credential")
    async def save_credential(provider_id: str, payload: CredentialUpsert):
        return service.upsert_credential(provider_id, payload.to_command())

    @router.post("/models/{model_id}/test")
    async def test_model(model_id: str, payload: ModelTestRequest):
        return await service.test_text_model(
            payload.provider_id,
            model_id,
            payload.prompt,
        )

    return router
