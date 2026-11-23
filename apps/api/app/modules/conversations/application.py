"""Conversation application use cases and streamed Agent orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.modules.conversations.commands import SendMessageCommand
from app.modules.conversations.domain import (
    TOOL_RUNTIME_VERSION,
    Conversation,
)
from app.modules.conversations.events import CodexEvent
from app.modules.conversations.ports import (
    CodexClient,
    ConversationModelGateway,
    ConversationRepositoryPort,
    ConversationTaskRecorder,
    ConversationWorkspacePort,
    ConversationWorkspaceQualityGate,
    CreativeProjectGateway,
)
from app.modules.conversations.runtime import ActiveTurn
from app.shared.errors import (
    AppServerError,
    ConversationBusyError,
    ConversationNotFoundError,
    DuplicateSubmissionError,
)
from app.shared.model_routing import TextModelRoute


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
        repository: ConversationRepositoryPort,
        codex_client: CodexClient,
        model_gateway: ConversationModelGateway | None = None,
        task_recorder: ConversationTaskRecorder | None = None,
        workspace_manager: ConversationWorkspacePort | None = None,
        creative_projects: CreativeProjectGateway | None = None,
        quality_gate: ConversationWorkspaceQualityGate | None = None,
    ) -> None:
        self._repository = repository
        self._codex = codex_client
        self._active_turns: dict[str, ActiveTurn] = {}
        self._models = model_gateway
        self._task_recorder = task_recorder
        self._workspace_manager = workspace_manager
        self._creative_projects = creative_projects
        self._quality_gate = quality_gate

    def list_conversations(self) -> list[dict[str, Any]]:
        return [
            {
                "id": conversation.id,
                "title": conversation.title,
                "status": conversation.status,
                "workspace": conversation.workspace_path,
                "threadId": conversation.thread_id,
                "messageCount": conversation.message_count,
                "updatedAt": conversation.last_activity_at,
                "projectId": conversation.project_id,
                "episodeId": conversation.episode_id,
                "scope": conversation.scope,
            }
            for conversation in self._repository.list_conversations()
        ]

    def recover_interrupted(self) -> int:
        """Close persisted turns whose in-memory streams were lost on restart."""

        self._active_turns.clear()
        return self._repository.recover_interrupted_turns()

    def create_conversation(
        self,
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        scope: str | None = None,
    ) -> dict[str, str | None]:
        conversation = self._repository.create_conversation(
            project_id=project_id,
            episode_id=episode_id,
            scope=scope,
        )
        workspace_path = None
        if self._workspace_manager:
            workspace_path = str(
                self._workspace_manager.ensure(conversation.id)
            )
            self._repository.set_workspace(conversation.id, workspace_path)
        return {
            "id": conversation.id,
            "title": conversation.title,
            "thread": conversation.thread_id,
            "workspace": workspace_path,
            "projectId": conversation.project_id,
            "episodeId": conversation.episode_id,
            "scope": conversation.scope,
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
        self, conversation_id: str, command: SendMessageCommand
    ) -> AsyncIterator[CodexEvent]:
        """Validate and schedule a turn before returning its SSE event iterator.

        Validation happens before the HTTP response starts, allowing the API layer
        to return meaningful 404/409 status codes instead of errors inside a 200
        streaming response.
        """

        conversation = self._require_conversation(conversation_id)
        if conversation_id in self._active_turns:
            raise ConversationBusyError("当前会话正在回复")
        if self._repository.submission_exists(command.client_message_id):
            raise DuplicateSubmissionError("消息已提交，请刷新查看结果")

        route: TextModelRoute | None = None
        if self._models:
            route = self._models.resolve_text_route(
                command.provider_id, command.model_id
            )

        project = None
        if command.creative_project_id and self._creative_projects:
            project = self._creative_projects.get_project(
                command.creative_project_id
            )
            if not project:
                raise ConversationNotFoundError("创作项目不存在")

        self._repository.start_submission(command.client_message_id, conversation_id)
        turn = self._repository.create_turn_with_messages(
            conversation_id, command.client_message_id, command.message
        )
        queue: asyncio.Queue[CodexEvent | None] = asyncio.Queue()
        active_turn = ActiveTurn(
            queue=queue,
            local_turn_id=turn.id,
            assistant_message_id=turn.assistant_message_id,
        )
        active_turn.route = route
        if project:
            active_turn.project_id = command.creative_project_id
            active_turn.workspace_path = str(project["workspacePath"])
        if route and self._task_recorder:
            active_turn.generation_task_id = self._task_recorder.start_text_task(
                conversation_id=conversation_id,
                turn_id=turn.id,
                prompt=visible_user_message(command.message),
                original_request=command.raw_request,
                route=route,
                client_request_id=command.client_message_id,
            )
        self._active_turns[conversation_id] = active_turn
        active_turn.task = asyncio.create_task(
            self._run_turn(conversation, command, active_turn)
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
            await asyncio.gather(active_turn.task, return_exceptions=True)
        return "interrupt_requested"

    def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._repository.get_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError("会话不存在")
        return conversation

    async def _run_turn(
        self,
        conversation: Conversation,
        command: SendMessageCommand,
        active_turn: ActiveTurn,
    ) -> None:
        """Bridge one Codex turn into the queue consumed by the SSE response."""

        error_message: str | None = None
        try:
            if active_turn.route and active_turn.route.runtime == "http":
                await self._run_http_model_turn(command, active_turn, active_turn.route)
                return
            await self._codex.start()
            workspace_path = active_turn.workspace_path or conversation.workspace_path
            if self._workspace_manager and not active_turn.project_id:
                workspace = self._workspace_manager.ensure(conversation.id)
                workspace_path = str(workspace)
                if conversation.workspace_path != workspace_path:
                    self._repository.set_workspace(
                        conversation.id,
                        workspace_path,
                    )
            workspace = Path(workspace_path) if workspace_path else None
            shared_roots = (
                [self._workspace_manager.shared_root]
                if self._workspace_manager
                else None
            )
            project_thread = (
                self._creative_projects.get_thread(active_turn.project_id)
                if active_turn.project_id and self._creative_projects
                else None
            )
            needs_tool_thread = (
                not conversation.thread_id
                or conversation.tool_runtime_version < TOOL_RUNTIME_VERSION
            )
            thread_id = project_thread or (
                await self._codex.create_thread(
                    cwd=workspace,
                    shared_roots=shared_roots,
                )
                if needs_tool_thread
                else conversation.thread_id
            )
            assert thread_id
            active_turn.thread_id = thread_id
            title = (
                derive_conversation_title(command.message)
                if not conversation.thread_id
                else conversation.title
            )
            if needs_tool_thread:
                self._repository.attach_thread(
                    conversation.id,
                    thread_id,
                    title,
                    tool_runtime_version=TOOL_RUNTIME_VERSION,
                )
            if active_turn.project_id and self._creative_projects:
                self._creative_projects.attach_thread(
                    active_turn.project_id,
                    thread_id,
                )

            async for event in self._codex.chat(
                command.message,
                thread_id,
                cwd=workspace,
                shared_roots=shared_roots,
            ):
                if event["type"] == "meta":
                    active_turn.thread_id = event["threadId"]
                    active_turn.turn_id = event["turnId"]
                    self._repository.set_codex_turn(
                        active_turn.local_turn_id or "", active_turn.turn_id
                    )
                    event["assistantMessageId"] = active_turn.assistant_message_id
                    self._repository.attach_thread(
                        conversation.id,
                        active_turn.thread_id,
                        title,
                        tool_runtime_version=TOOL_RUNTIME_VERSION,
                    )
                if event["type"] == "delta" and event.get("text"):
                    self._repository.append_assistant_content(
                        active_turn.assistant_message_id or "", event["text"]
                    )
                if event["type"] == "message_completed":
                    self._repository.replace_assistant_content(
                        active_turn.assistant_message_id or "", event.get("text", "")
                    )
                if event["type"] == "output":
                    self._repository.replace_assistant_content(
                        active_turn.assistant_message_id or "",
                        str(event.get("content") or ""),
                    )
                    self._repository.replace_reasoning(
                        active_turn.local_turn_id or "",
                        str(event.get("reasoning") or ""),
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
            if (
                active_turn.project_id
                and active_turn.workspace_path
                and self._creative_projects
            ):
                project_workspace = Path(active_turn.workspace_path)
                if self._quality_gate:
                    quality = self._quality_gate.inspect(project_workspace)
                    self._quality_gate.write_report(project_workspace, quality)
                else:
                    quality = {}
                sync = self._creative_projects.reconcile_workspace(
                    active_turn.project_id
                )
                document_url = (
                    f"/api/creative-projects/{active_turn.project_id}/files/"
                    "exports/novel-project.md"
                )
                self._repository.append_assistant_content(
                    active_turn.assistant_message_id or "",
                    f"\n\n[打开完整项目文档]({document_url})",
                )
                await active_turn.queue.put(
                    {
                        "type": "project_sync",
                        "projectId": active_turn.project_id,
                        "documentUrl": document_url,
                        "quality": quality,
                        **sync,
                    }
                )
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
            self._repository.finish_submission(command.client_message_id)
            if active_turn.generation_task_id and active_turn.route and self._task_recorder:
                self._task_recorder.finish_text_task(
                    active_turn.generation_task_id,
                    status="failed" if error_message else "completed",
                    route=active_turn.route,
                    error=error_message,
                )
            await active_turn.queue.put(None)

    async def _run_http_model_turn(
        self,
        command: SendMessageCommand,
        active_turn: ActiveTurn,
        route: TextModelRoute,
    ) -> None:
        """Stream an external model through the provider gateway port."""

        assert self._models is not None
        model = route.provider_model
        if active_turn.generation_task_id and self._task_recorder:
            self._task_recorder.update_text_task_request(
                active_turn.generation_task_id,
                {
                    "model": model["model_key"],
                    "messages": [{"role": "user", "content": command.message}],
                    "stream": True,
                },
            )
        await active_turn.queue.put(
            {
                "type": "meta",
                "provider": route.provider_id,
                "model": model["model_key"],
                "assistantMessageId": active_turn.assistant_message_id,
            }
        )
        async for event in self._models.stream_text(route, command.message):
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


def derive_conversation_title(message: str) -> str:
    text = message.strip()
    marker = "【短剧工作台上下文】"
    if text.startswith(marker):
        header, _, body = text.partition("用户消息：")
        fields: dict[str, str] = {}
        for line in header.splitlines()[1:]:
            key, separator, value = line.partition("：")
            if not separator:
                continue
            fields[key.strip()] = value.strip()
        scope = fields.get("当前范围", "短剧")
        stage = fields.get("当前阶段", "").split("（", 1)[0].strip()
        parts = ["短剧"]
        if scope and scope != "全局项目":
            parts.append(scope)
        if stage:
            parts.append(stage)
        title = " · ".join(dict.fromkeys(parts))
        if body.strip():
            return title[:80]
    visible = visible_user_message(text)
    first_line = next(
        (line.strip() for line in visible.splitlines() if line.strip()),
        "新的创意对话",
    )
    return first_line[:40]


def visible_user_message(message: str) -> str:
    text = message.strip()
    if not text.startswith("【短剧工作台上下文】"):
        return text
    _, _, body = text.partition("用户消息：")
    return body.strip() or text
