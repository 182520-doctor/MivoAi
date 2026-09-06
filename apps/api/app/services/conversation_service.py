"""Conversation use cases spanning persistence and Codex streaming."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.exceptions import (
    AppServerError,
    ConversationBusyError,
    ConversationNotFoundError,
    DuplicateSubmissionError,
    ProviderConfigurationError,
)
from app.core.interfaces import CodexClient
from app.db.repositories import ConversationRepository
from app.models.codex import CodexEvent
from app.models.conversation import ActiveTurn, Conversation, MessageCreate
from app.services.provider_service import ProviderService
from app.services.volcengine import VolcengineChatClient


async def request_turn_interrupt(
    codex_client: CodexClient, active_turn: ActiveTurn
) -> None:
    """Send an idempotent interrupt when App Server has assigned a turn ID."""

    active_turn.stop_requested = True
    if not active_turn.thread_id or not active_turn.turn_id:
        return
    try:
        await codex_client.request(
            "turn/interrupt",
            {"threadId": active_turn.thread_id, "turnId": active_turn.turn_id},
        )
    except AppServerError as exc:
        if "no active turn" not in str(exc).lower():
            raise


class ConversationService:
    """Coordinate conversations without depending on FastAPI or raw SQL."""

    def __init__(
        self,
        repository: ConversationRepository,
        codex_client: CodexClient,
        provider_service: ProviderService | None = None,
        volcengine_client: VolcengineChatClient | None = None,
    ) -> None:
        self._repository = repository
        self._codex = codex_client
        self._active_turns: dict[str, ActiveTurn] = {}
        self._providers = provider_service
        self._volcengine = volcengine_client or VolcengineChatClient()

    def list_conversations(self) -> list[dict[str, str]]:
        return [
            {"id": conversation.id, "title": conversation.title, "status": conversation.status}
            for conversation in self._repository.list_conversations()
        ]

    def create_conversation(self) -> dict[str, str | None]:
        conversation = self._repository.create_conversation()
        return {
            "id": conversation.id,
            "title": conversation.title,
            "thread": conversation.thread_id,
        }

    async def get_history(
        self, conversation_id: str, cursor: str | None = None
    ) -> dict[str, Any]:
        self._require_conversation(conversation_id)
        messages = self._repository.list_messages(conversation_id)
        return {
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "status": message.status,
                    "reasoning": message.reasoning,
                    "reasoningTokens": message.reasoning_tokens,
                }
                for message in messages
            ],
            "cursor": None,
            "active": conversation_id in self._active_turns,
        }

    async def start_message(
        self, conversation_id: str, payload: MessageCreate
    ) -> AsyncIterator[CodexEvent]:
        """Validate and schedule a turn before returning its SSE event iterator.

        Validation happens before the HTTP response starts, allowing the API layer
        to return meaningful 404/409 status codes instead of errors inside a 200
        streaming response.
        """

        conversation = self._require_conversation(conversation_id)
        if conversation_id in self._active_turns:
            raise ConversationBusyError("当前会话正在回复")
        if self._repository.submission_exists(payload.clientMessageId):
            raise DuplicateSubmissionError("消息已提交，请刷新查看结果")

        selected: dict[str, object] | None = None
        if self._providers:
            selected = self._providers.resolve_text_model(payload.modelId)
            if payload.providerId != selected["provider_id"]:
                raise ProviderConfigurationError("所选模型不属于指定供应商")

        self._repository.start_submission(payload.clientMessageId, conversation_id)
        turn = self._repository.create_turn_with_messages(
            conversation_id, payload.clientMessageId, payload.message
        )
        queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        active_turn = ActiveTurn(
            queue=queue,
            local_turn_id=turn.id,
            assistant_message_id=turn.assistant_message_id,
        )
        if selected:
            active_turn.provider_id = str(selected["provider_id"])
            active_turn.model_id = str(selected["id"])
            active_turn.provider_model = selected
            active_turn.generation_task_id = self._repository.create_generation_task(
                session_id=conversation_id,
                turn_id=turn.id,
                user_id="local-user",
                provider_id=active_turn.provider_id,
                model_id=active_turn.model_id,
                prompt=payload.message,
                original_request=payload.model_dump(by_alias=True),
                normalized_request={
                    "providerId": active_turn.provider_id,
                    "modelId": active_turn.model_id,
                    "taskType": "text",
                },
                client_request_id=payload.clientMessageId,
            )
        self._active_turns[conversation_id] = active_turn
        active_turn.task = asyncio.create_task(
            self._run_turn(conversation, payload, active_turn)
        )
        return self._consume_events(queue)

    async def interrupt(self, conversation_id: str) -> str:
        """Request cancellation and end the browser stream immediately.

        App Server can report that a turn already ended while an interrupt was in
        flight. Treating that response as success makes this operation idempotent.
        """

        self._require_conversation(conversation_id)
        active_turn = self._active_turns.get(conversation_id)
        if not active_turn:
            return "idle"

        await request_turn_interrupt(self._codex, active_turn)

        await active_turn.queue.put({"type": "done", "status": "interrupted"})
        if active_turn.task:
            active_turn.task.cancel()
        return "interrupt_requested"

    def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError("会话不存在")
        return conversation

    async def _run_turn(
        self,
        conversation: Conversation,
        payload: MessageCreate,
        active_turn: ActiveTurn,
    ) -> None:
        """Bridge one Codex turn into the queue consumed by the SSE response."""

        error_message: str | None = None
        try:
            if active_turn.provider_id == "volcengine" and active_turn.provider_model:
                await self._run_volcengine_turn(payload, active_turn, active_turn.provider_model)
                return
            await self._codex.start()
            thread_id = conversation.thread_id or await self._codex.create_thread()
            active_turn.thread_id = thread_id
            title = payload.message[:40] if not conversation.thread_id else conversation.title
            self._repository.attach_thread(conversation.id, thread_id, title)

            async for event in self._codex.chat(payload.message, thread_id):
                if event["type"] == "meta":
                    active_turn.turn_id = event["turnId"]
                    self._repository.set_codex_turn(
                        active_turn.local_turn_id or "", active_turn.turn_id
                    )
                    event["assistantMessageId"] = active_turn.assistant_message_id
                if event["type"] == "delta" and event.get("text"):
                    self._repository.append_assistant_content(
                        active_turn.assistant_message_id or "", event["text"]
                    )
                if event["type"] == "message_completed":
                    self._repository.replace_assistant_content(
                        active_turn.assistant_message_id or "", event.get("text", "")
                    )
                if event["type"] == "reasoning_delta" and event.get("text"):
                    self._repository.append_reasoning(
                        active_turn.local_turn_id or "", event["text"]
                    )
                if event["type"] == "reasoning_completed" and event.get("text"):
                    self._repository.replace_reasoning(
                        active_turn.local_turn_id or "", event["text"]
                    )
                if event["type"] == "reasoning_usage":
                    self._repository.update_reasoning_tokens(
                        active_turn.local_turn_id or "", int(event.get("tokens") or 0)
                    )
                if event["type"] == "error":
                    error_message = str(event.get("message") or "Codex 回复失败")
                await active_turn.queue.put(event)
        except Exception as exc:  # noqa: BLE001 - transport errors become terminal SSE events
            error_message = str(exc)
            await active_turn.queue.put({"type": "error", "message": str(exc)})
        finally:
            # Remove only our own state so a later turn can never be popped by a
            # delayed cleanup task from an earlier request.
            if self._active_turns.get(conversation.id) is active_turn:
                self._active_turns.pop(conversation.id, None)
            if active_turn.local_turn_id and active_turn.assistant_message_id:
                if error_message:
                    status = "failed"
                elif active_turn.stop_requested:
                    status = "interrupted"
                else:
                    status = "completed"
                self._repository.finish_turn(
                    conversation.id,
                    active_turn.local_turn_id,
                    active_turn.assistant_message_id,
                    status,
                    error_message,
                )
            self._repository.finish_submission(payload.clientMessageId)
            if active_turn.generation_task_id:
                self._repository.finish_generation_task(
                    active_turn.generation_task_id,
                    status="failed" if error_message else "completed",
                    response={"provider": active_turn.provider_id, "model": active_turn.model_id},
                    error=error_message,
                )
            await active_turn.queue.put(None)

    async def _run_volcengine_turn(
        self,
        payload: MessageCreate,
        active_turn: ActiveTurn,
        model: dict[str, object],
    ) -> None:
        """Stream Ark Chat API events through the existing SSE contract."""

        api_key = str(model.get("api_key") or "")
        config = json.loads(str(model.get("config_json") or "{}"))
        base_url = str(
            config.get("base_url")
            or model.get("base_url")
            or "https://ark.cn-beijing.volces.com/api/v3"
        )
        if active_turn.generation_task_id:
            self._repository.update_generation_task_request(
                active_turn.generation_task_id,
                {
                    "model": model["model_key"],
                    "messages": [{"role": "user", "content": payload.message}],
                    "stream": True,
                },
            )
        await active_turn.queue.put(
            {
                "type": "meta",
                "provider": "volcengine",
                "model": model["model_key"],
                "assistantMessageId": active_turn.assistant_message_id,
            }
        )
        async for event in self._volcengine.chat(
            api_key=api_key,
            base_url=base_url,
            model=str(model["model_key"]),
            message=payload.message,
        ):
            if event.get("type") == "delta" and event.get("text"):
                self._repository.append_assistant_content(
                    active_turn.assistant_message_id or "", str(event["text"])
                )
            if event.get("type") == "reasoning_delta" and event.get("text"):
                self._repository.append_reasoning(
                    active_turn.local_turn_id or "", str(event["text"])
                )
            await active_turn.queue.put(event)

    @staticmethod
    async def _consume_events(
        queue: asyncio.Queue[CodexEvent | None],
    ) -> AsyncIterator[CodexEvent]:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
