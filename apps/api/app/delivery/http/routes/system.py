"""HTTP routes for operational health and compatibility."""

from fastapi import APIRouter, HTTPException, Request

from app.delivery.http.schemas.conversations import LegacyChatRequest
from app.modules.conversations.ports import CodexClient


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
            "recoveredConversationTurns": getattr(
                request.app.state,
                "recovered_conversation_turns",
                0,
            ),
        }

    @router.post("/api/chat")
    async def removed_legacy_chat(_: LegacyChatRequest):
        """Return a clear migration response for clients using the old endpoint."""

        raise HTTPException(410, "请使用网站会话接口")

    return router
