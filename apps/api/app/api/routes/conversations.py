"""HTTP endpoints for conversation lifecycle and streaming messages."""

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.exceptions import (
    AppServerError,
    ConversationBusyError,
    ConversationNotFoundError,
    DuplicateSubmissionError,
    ProviderConfigurationError,
)
from app.core.security import is_origin_allowed
from app.models.conversation import MessageCreate
from app.services.conversation_service import ConversationService


def create_conversation_router(
    service: ConversationService, allowed_origins: tuple[str, ...]
) -> APIRouter:
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
    async def removed_stream(conversation_id: str):
        raise HTTPException(
            410, "请使用 WebSocket /api/conversations/{conversation_id}/ws"
        )

    @router.websocket("/{conversation_id}/ws")
    async def stream_messages(websocket: WebSocket, conversation_id: str):
        if not is_origin_allowed(websocket.headers.get("origin"), allowed_origins):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        receiver: asyncio.Task | None = None
        sender: asyncio.Task | None = None
        owns_turn = False

        async def report_error(exc: Exception, request_id: str | None = None):
            code = 422
            if isinstance(exc, ConversationNotFoundError):
                code = 404
            elif isinstance(exc, (ConversationBusyError, DuplicateSubmissionError)):
                code = 409
            elif isinstance(exc, ProviderConfigurationError):
                code = 400
            elif isinstance(exc, AppServerError):
                code = 502
            await websocket.send_json({
                "type": "error", "code": code, "message": str(exc),
                "clientMessageId": request_id,
            })

        async def forward(events, request_id):
            # Publish terminal events only after persistence and cleanup finish.
            terminal = None
            async for event in events:
                if event["type"] in {"done", "error"}:
                    terminal = event
                else:
                    await websocket.send_json({**event, "clientMessageId": request_id})
            if terminal:
                await websocket.send_json({**terminal, "clientMessageId": request_id})

        try:
            try:
                await service.get_history(conversation_id)
            except ConversationNotFoundError as exc:
                await report_error(exc)
                await websocket.close(code=1008)
                return
            await websocket.send_json({"type": "ready", "conversationId": conversation_id})
            receiver = asyncio.create_task(websocket.receive_json())
            while True:
                pending = [receiver] + ([sender] if sender else [])
                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                if sender and sender in done:
                    sender.result()
                    sender = None
                    owns_turn = False
                if receiver not in done:
                    continue
                request_id = None
                try:
                    command = receiver.result()
                    if not isinstance(command, dict):
                        raise ValueError("消息必须为 JSON 对象")
                    if command.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif command.get("type") == "interrupt":
                        if owns_turn:
                            await service.interrupt(conversation_id)
                    elif command.get("type") == "message":
                        raw_payload = command.get("payload")
                        if isinstance(raw_payload, dict):
                            request_id = raw_payload.get("clientMessageId")
                        payload = MessageCreate.model_validate(command.get("payload"))
                        request_id = payload.clientMessageId
                        if sender:
                            raise ConversationBusyError("当前会话正在回复")
                        events = await service.start_message(conversation_id, payload)
                        owns_turn = True
                        sender = asyncio.create_task(forward(events, request_id))
                    else:
                        raise ValueError("未知消息类型")
                except (
                    ValueError, ValidationError, ConversationNotFoundError,
                    ConversationBusyError, DuplicateSubmissionError, AppServerError,
                ) as exc:
                    await report_error(exc, request_id)
                receiver = asyncio.create_task(websocket.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            tasks = [task for task in (receiver, sender) if task]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if owns_turn:
                await service.interrupt(conversation_id)

    return router
