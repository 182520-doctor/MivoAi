"""Operational health and backward-compatibility endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.core.interfaces import CodexClient
from app.models.conversation import LegacyChatRequest


def create_status_router(codex_client: CodexClient) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/api/status")
    @router.get("/health")
    async def health(request: Request):
        status = codex_client.status()
        return {
            "status": "ok" if status["running"] else "degraded",
            "app_server": status,
            "error": getattr(request.app.state, "startup_error", None),
        }

    @router.post("/api/chat")
    async def removed_legacy_chat(_: LegacyChatRequest):
        """Return a clear migration response for clients using the old endpoint."""

        raise HTTPException(410, "请使用网站会话接口")

    return router
