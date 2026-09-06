"""Asynchronous JSON-RPC client for the local Codex App Server process.

This module owns the subprocess transport and protocol routing only. Conversation
and HTTP concerns live in their own layers, which keeps Codex protocol changes
isolated from the public API.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.core.exceptions import AppServerError
from app.core.protocol_logging import create_protocol_logger, redact_protocol_value
from app.models.codex import CodexEvent


class CodexAppServerClient:
    """Manage one App Server process and multiplex JSON-RPC events by thread."""

    def __init__(
        self,
        binary: Path,
        workspace: Path,
        protocol_log: Path,
        protocol_logging_enabled: bool = True,
    ) -> None:
        self.binary = binary
        self.workspace = workspace
        self.process: asyncio.subprocess.Process | None = None
        self.server_info: dict[str, Any] | None = None
        self.account: dict[str, Any] | None = None

        # JSON-RPC responses only carry numeric IDs. Futures connect each response
        # back to the coroutine that issued the corresponding request.
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}

        # App Server notifications are routed by thread ID. Each active chat turn
        # subscribes with its own queue so independent conversations do not mix.
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._loaded_threads: set[str] = set()

        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._start_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._stderr_tail: deque[str] = deque(maxlen=30)
        self._protocol_logger = (
            create_protocol_logger(protocol_log) if protocol_logging_enabled else None
        )

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    @property
    def authenticated(self) -> bool:
        return self.account is not None

    def _log_protocol(self, direction: str, payload: Any) -> None:
        """Write one sanitized protocol record to both console and log file."""

        if not self._protocol_logger:
            return
        rendered = json.dumps(redact_protocol_value(payload), ensure_ascii=False)
        self._protocol_logger.info("[Codex %s] %s", direction, rendered)

    async def start(self) -> None:
        """Start and initialize App Server once, even under concurrent requests."""

        async with self._start_lock:
            if self.running:
                return
            if not self.binary.is_file():
                raise AppServerError(f"Codex binary not found: {self.binary}")

            self.workspace.mkdir(parents=True, exist_ok=True)
            self._loaded_threads.clear()
            self.process = await asyncio.create_subprocess_exec(
                str(self.binary),
                "app-server",
                "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            self._log_protocol(
                "lifecycle",
                {"event": "started", "pid": self.process.pid, "binary": str(self.binary)},
            )
            self._reader_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())

            self.server_info = await self.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "zaojing_web",
                        "title": "Zaojing Web",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self.notify("initialized", {})
            account_result = await self.request(
                "account/read", {"refreshToken": False}, timeout=20
            )
            self.account = account_result.get("account")

    async def stop(self) -> None:
        """Stop App Server and release background reader tasks."""

        process = self.process
        self.process = None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
        for task in (self._reader_task, self._stderr_task):
            if task:
                task.cancel()
        self._reader_task = None
        self._stderr_task = None
        self._log_protocol("lifecycle", {"event": "stopped"})

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and await the response with the matching ID."""

        if not self.running or not self.process or not self.process.stdin:
            raise AppServerError("Codex App Server is not running")

        self._request_id += 1
        request_id = self._request_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._send({"method": method, "id": request_id, "params": params or {}})
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)
        if "error" in response:
            error = response["error"]
            raise AppServerError(error.get("message", str(error)))
        return response.get("result", {})

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification, which intentionally has no request ID."""

        await self._send({"method": method, "params": params})

    async def create_thread(self) -> str:
        """Create a persistent, read-only Codex thread for creative conversation."""

        result = await self.request(
            "thread/start",
            {
                "cwd": str(self.workspace),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "personality": "friendly",
                "ephemeral": False,
                "environments": [],
                "selectedCapabilityRoots": [],
                "config": {"features.shell_tool": False, "web_search": "disabled"},
                "serviceName": "zaojing_web",
                "developerInstructions": (
                    "你是造境网站里的创意沟通助手。使用中文简洁回答，帮助用户梳理创意、"
                    "完善需求和形成可执行方案。当前是纯聊天模式：不要调用工具，不要执行命令，"
                    "不要读写文件。如果用户要求你实际操作，说明当前版本只支持沟通。"
                ),
            },
        )
        thread_id = result["thread"]["id"]
        self._loaded_threads.add(thread_id)
        return thread_id

    async def chat(
        self, message: str, thread_id: str | None
    ) -> AsyncIterator[CodexEvent]:
        """Start one turn and normalize relevant App Server notifications."""

        await self.start()
        active_thread_id = thread_id or await self.create_thread()

        # Threads restored from SQLite must be resumed after a process restart.
        # A newly created thread is already loaded and must not be resumed early.
        if thread_id and thread_id not in self._loaded_threads:
            await self.request(
                "thread/resume",
                {
                    "threadId": thread_id,
                    "excludeTurns": True,
                    "sandbox": "read-only",
                    "approvalPolicy": "never",
                },
            )
            self._loaded_threads.add(thread_id)

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(active_thread_id, set()).add(queue)
        try:
            result = await self.request(
                "turn/start",
                {
                    "threadId": active_thread_id,
                    "input": [{"type": "text", "text": message}],
                    "environments": [],
                },
                timeout=30,
            )
            turn_id = result["turn"]["id"]
            yield {"type": "meta", "threadId": active_thread_id, "turnId": turn_id}

            while True:
                event = await asyncio.wait_for(queue.get(), timeout=180)
                normalized = self._normalize_turn_event(event, turn_id)
                if normalized:
                    yield normalized
                    if normalized["type"] in {"done", "error"}:
                        break
        except TimeoutError as exc:
            raise AppServerError("等待 Codex 回复超时") from exc
        finally:
            subscribers = self._subscribers.get(active_thread_id)
            if subscribers:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(active_thread_id, None)

    @staticmethod
    def _normalize_turn_event(
        event: dict[str, Any], turn_id: str
    ) -> CodexEvent | None:
        """Reduce verbose protocol notifications to the events consumed by the UI."""

        method = event.get("method")
        params = event.get("params", {})
        if params.get("turnId") not in (None, turn_id):
            return None
        if method == "item/agentMessage/delta":
            return {
                "type": "delta",
                "text": params.get("delta", ""),
                "itemId": params.get("itemId"),
            }
        if method == "item/started" and params.get("item", {}).get("type") == "reasoning":
            item = params["item"]
            return {
                "type": "reasoning_started",
                "text": _extract_reasoning_text(item),
                "itemId": item.get("id"),
            }
        if method in {
            "item/reasoning/delta",
            "item/reasoningSummary/delta",
            "item/agentReasoning/delta",
        }:
            return {
                "type": "reasoning_delta",
                "text": params.get("delta", ""),
                "itemId": params.get("itemId"),
            }
        if method == "item/completed" and params.get("item", {}).get("type") == "reasoning":
            item = params["item"]
            return {
                "type": "reasoning_completed",
                "text": _extract_reasoning_text(item),
                "itemId": item.get("id"),
            }
        if method == "thread/tokenUsage/updated":
            usage = params.get("tokenUsage", {}).get("last", {})
            reasoning_tokens = usage.get("reasoningOutputTokens", 0)
            return {"type": "reasoning_usage", "tokens": reasoning_tokens}
        if method == "item/completed" and params.get("item", {}).get("type") == "agentMessage":
            item = params["item"]
            return {
                "type": "message_completed",
                "text": item["text"],
                "itemId": item["id"],
            }
        if method == "turn/completed":
            turn = params.get("turn", {})
            if turn.get("status") == "failed":
                error = turn.get("error") or {}
                return {"type": "error", "message": error.get("message", "Codex 回复失败")}
            return {"type": "done", "status": turn.get("status", "completed")}
        return None

    async def _send(self, payload: dict[str, Any]) -> None:
        """Serialize writes because asyncio subprocess stdin is a shared stream."""

        if not self.process or not self.process.stdin:
            raise AppServerError("Codex App Server stdin is unavailable")
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        self._log_protocol("gateway -> app-server", payload)
        async with self._write_lock:
            self.process.stdin.write(encoded)
            await self.process.stdin.drain()

    async def _read_stdout(self) -> None:
        """Continuously route responses, server requests, and notifications."""

        assert self.process and self.process.stdout
        while line := await self.process.stdout.readline():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._log_protocol(
                    "app-server -> gateway",
                    {"invalidJson": line.decode(errors="replace").rstrip()},
                )
                continue
            self._log_protocol("app-server -> gateway", message)
            request_id = message.get("id")
            if request_id is not None and ("result" in message or "error" in message):
                future = self._pending.get(request_id)
                if future and not future.done():
                    future.set_result(message)
                continue
            if request_id is not None and message.get("method"):
                await self._handle_server_request(message)
                continue
            thread_id = message.get("params", {}).get("threadId")
            if thread_id:
                for subscriber in list(self._subscribers.get(thread_id, set())):
                    subscriber.put_nowait(message)

        # Wake every waiter if the subprocess exits, otherwise SSE requests could
        # remain blocked until their full timeout expires.
        disconnected = {
            "method": "turn/completed",
            "params": {
                "turn": {
                    "status": "failed",
                    "error": {"message": "App Server 连接中断"},
                }
            },
        }
        for subscribers in self._subscribers.values():
            for subscriber in subscribers:
                subscriber.put_nowait(disconnected)
        error = AppServerError("Codex App Server stopped unexpectedly")
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)

    async def _read_stderr(self) -> None:
        """Retain recent diagnostics and mirror them to the protocol log."""

        assert self.process and self.process.stderr
        while line := await self.process.stderr.readline():
            rendered = line.decode(errors="replace").rstrip()
            self._stderr_tail.append(rendered)
            self._log_protocol("app-server stderr", {"message": rendered})

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        """Fail closed for approvals because this MVP is intentionally read-only."""

        method = message.get("method", "")
        if method.startswith("item/") and method.endswith("/requestApproval"):
            result: dict[str, Any] = {"decision": "decline"}
        elif method == "item/tool/requestUserInput":
            result = {"answers": {}}
        else:
            result = {"decision": "cancel"}
        await self._send({"id": message["id"], "result": result})

    def status(self) -> dict[str, Any]:
        """Return non-sensitive process and authentication health information."""

        return {
            "running": self.running,
            "authenticated": self.authenticated,
            "version": self.server_info.get("userAgent") if self.server_info else None,
            "platform": self.server_info.get("platformOs") if self.server_info else None,
            "binary": str(self.binary),
        }


def _extract_reasoning_text(item: dict[str, Any]) -> str:
    """Best-effort extraction for reasoning payloads across App Server versions.

    Current local App Server builds often expose only the reasoning item lifecycle
    and token counts, with empty `summary` and `content` arrays. Keeping this
    parser broad makes the gateway ready for versions that do stream summaries.
    """

    fragments: list[str] = []
    for key in ("summary", "content"):
        value = item.get(key)
        if isinstance(value, str):
            fragments.append(value)
        elif isinstance(value, list):
            fragments.extend(_extract_text_from_list(value))
    return "\n".join(fragment for fragment in fragments if fragment).strip()


def _extract_text_from_list(values: list[Any]) -> list[str]:
    fragments: list[str] = []
    for value in values:
        if isinstance(value, str):
            fragments.append(value)
        elif isinstance(value, dict):
            text = value.get("text") or value.get("content") or value.get("summary")
            if isinstance(text, str):
                fragments.append(text)
            elif isinstance(text, list):
                fragments.extend(_extract_text_from_list(text))
    return fragments
