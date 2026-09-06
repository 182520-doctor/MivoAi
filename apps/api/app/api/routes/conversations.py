"""HTTP endpoints for conversation lifecycle and streaming messages."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.conversation import MessageCreate
from app.services.conversation_service import ConversationService
from app.utils.sse import encode_sse


def create_conversation_router(service: ConversationService) -> APIRouter:
    """Create a router with its business dependency supplied at startup."""

    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    @router.get("")
    async def list_conversations():
        return service.list_conversations()

    @router.post("")
    async def create_conversation():
        return service.create_conversation()

    @router.get("/{conversation_id}/messages")
    async def get_history(conversation_id: str, cursor: str | None = None):
        return await service.get_history(conversation_id, cursor)

    @router.post("/{conversation_id}/interrupt")
    async def interrupt(conversation_id: str):
        status = await service.interrupt(conversation_id)
        return {"status": status}

    @router.post("/{conversation_id}/messages")
    async def send_message(
        conversation_id: str, payload: MessageCreate
    ) -> StreamingResponse:
        events = await service.start_message(conversation_id, payload)

        async def event_stream():
            async for event in events:
                yield encode_sse(event)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
