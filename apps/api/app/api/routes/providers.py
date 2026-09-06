"""HTTP routes for the model catalog and local provider settings."""

from fastapi import APIRouter

from app.models.gateway import CredentialUpsert, PreferenceUpdate
from app.services.provider_service import ProviderService


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
        return service.update_preferences(payload)

    @router.put("/providers/{provider_id}/credential")
    async def save_credential(provider_id: str, payload: CredentialUpsert):
        return service.upsert_credential(provider_id, payload)

    return router
