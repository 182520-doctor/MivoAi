"""Asynchronous JSON-RPC client for the local Codex App Server process.

This module owns the subprocess transport and protocol routing only. Conversation
and HTTP concerns live in their own layers, which keeps Codex protocol changes
isolated from the public API.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.core.exceptions import AppServerError
from app.core.protocol_logging import create_protocol_logger, redact_protocol_value
from app.models.codex import CodexEvent
from app.services.codex_events import TurnEventNormalizer


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
        self.requires_openai_auth: bool | None = None

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
        """Whether the provider's OpenAI authentication requirement is satisfied."""

        return self.account is not None or self.requires_openai_auth is False

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
            self.account = None
            self.requires_openai_auth = None
            if not self.binary.is_file():
                raise AppServerError(f"Codex binary not found: {self.binary}")
            host = self._code_mode_host_path()
            if not host.is_file():
                raise AppServerError(
                    "Codex 执行组件缺失："
                    f"{host}。请安装与当前 Codex 版本和平台匹配的 "
                    "codex-code-mode-host，或通过 CODEX_BINARY 指向完整的 Codex 安装。"
                )

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
                **_subprocess_startup_options(),
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
            self.requires_openai_auth = account_result.get("requiresOpenaiAuth")

    async def stop(self) -> None:
        """Stop App Server and release background reader tasks."""

        process = self.process
        self.process = None
        self.account = None
        self.requires_openai_auth = None
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

    async def create_thread(self, workspace: Path | None = None) -> str:
        """Create an in-memory website thread bound to a project workspace.

        Website conversations are persisted by this application's SQLite database.
        Keeping the underlying Codex thread ephemeral prevents them from appearing
        in the user's Codex desktop task history.
        """
        thread_workspace = workspace or self.workspace

        result = await self.request(
            "thread/start",
            {
                "cwd": str(thread_workspace),
                "approvalPolicy": "never",
                "sandbox": "workspace-write",
                "personality": "friendly",
                "ephemeral": True,
                "environments": [],
                "selectedCapabilityRoots": [],
                "config": {"features.shell_tool": False, "web_search": "disabled"},
                "serviceName": "zaojing_web",
                "developerInstructions": (
                    "你是造境网站里的创意导演 Agent。使用中文回答，帮助用户把一个模糊创意"
                    "推进到可执行的内容方案、完整剧本、分镜草案或拍摄说明。"
                    "涉及创作项目时，先读取当前工作空间中的 project.json、AGENTS.md、"
                    "state/workflow.json、skills/novel-writing/SKILL.md、knowledge/"
                    " 和已确认产物，再将阶段结果写回工作空间；"
                    "普通聊天不要修改项目文件，也不要承诺实际生成图片或视频。"
                    "只使用受限工作空间内的文件和命令工具；不要调用 Finder、PyCharm、"
                    "浏览器控制或 Computer Use，也不要要求用户授予 GUI 权限。"
                    "当用户要写剧本或做短片时，按导演工作流处理：默认自动补全合理信息并连续执行，"
                    "不要把每个阶段都交给用户确认。只有缺少信息会导致作品无法成立、涉及重大方向冲突、"
                    "或用户明确要求确认时，才暂停并提出最多 3 个关键问题；"
                    "其余情况直接完成完整结构。"
                    "输出应包括："
                    "创意定位、受众与时长、核心冲突、人物设定、三幕或起承转合结构、完整剧本"
                    "正文、关键镜头/场景调度、声音与情绪设计、可继续追问的修改方向。"
                    "不要暴露隐藏推理，但可以在正文中提供简短的创作判断和取舍说明。"
                ),
            },
        )
        thread_id = result["thread"]["id"]
        self._loaded_threads.add(thread_id)
        return thread_id

    async def chat(
        self,
        message: str,
        thread_id: str | None,
        workspace: Path | None = None,
    ) -> AsyncIterator[CodexEvent]:
        """Start one turn and normalize relevant App Server notifications."""

        await self.start()
        # Ephemeral threads only live for the lifetime of this App Server process.
        # After a backend restart, replace the SQLite reference with a fresh thread
        # instead of resuming an old persistent Codex desktop conversation.
        active_thread_id = (
            thread_id
            if thread_id and thread_id in self._loaded_threads
            else await self.create_thread(workspace)
        )

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(active_thread_id, set()).add(queue)
        try:
            result = await self.request(
                "turn/start",
                {
                    "threadId": active_thread_id,
                    "input": [{"type": "text", "text": message}],
                    "cwd": str((workspace or self.workspace).resolve()),
                    "approvalPolicy": "never",
                    "sandboxPolicy": self._workspace_sandbox_policy(workspace),
                    "environments": [],
                },
                timeout=30,
            )
            turn_id = result["turn"]["id"]
            yield {"type": "meta", "threadId": active_thread_id, "turnId": turn_id}

            normalizer = TurnEventNormalizer(turn_id, user_message=message)
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=600)
                normalized = normalizer.normalize(event)
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

        # Wake every waiter if the subprocess exits, otherwise chat requests could
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
            "accountAuthenticated": self.account is not None,
            "requiresOpenaiAuth": self.requires_openai_auth,
            "version": self.server_info.get("userAgent") if self.server_info else None,
            "platform": self.server_info.get("platformOs") if self.server_info else None,
            "binary": str(self.binary),
            "codeModeHost": str(self._code_mode_host_path()),
            "codeModeHostAvailable": self._code_mode_host_path().is_file(),
        }

    def _code_mode_host_path(self) -> Path:
        suffix = ".exe" if os.name == "nt" else ""
        return self.binary.parent / f"codex-code-mode-host{suffix}"

    def _workspace_sandbox_policy(self, workspace: Path | None) -> dict[str, Any]:
        """Limit writes to the selected website or creative-project workspace."""

        writable_root = (workspace or self.workspace).resolve()
        writable_root.mkdir(parents=True, exist_ok=True)
        return {
            "type": "workspaceWrite",
            "writableRoots": [str(writable_root)],
            "networkAccess": False,
            "excludeTmpdirEnvVar": False,
            "excludeSlashTmp": False,
        }




def _subprocess_startup_options() -> dict[str, int]:
    if os.name != "nt":
        return {}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", None)
    return {"creationflags": create_no_window} if create_no_window is not None else {}
