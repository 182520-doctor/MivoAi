import asyncio
from pathlib import Path

from app.contexts.conversations.application import ConversationService
from app.contexts.conversations.domain import TOOL_RUNTIME_VERSION
from app.contexts.conversations.infrastructure.codex_app_server import (
    CodexAppServerClient,
)
from app.contexts.conversations.infrastructure.repository import ConversationRepository
from app.contexts.conversations.workspace import ConversationWorkspaceManager
from app.infrastructure.persistence.database import Database
from tests.fakes import FakeCodexClient


def test_conversation_has_isolated_workspace_and_shared_playbooks(tmp_path) -> None:
    database = Database(tmp_path / "conversation.db")
    repository = ConversationRepository(database)
    manager = ConversationWorkspaceManager(tmp_path / "workspace")
    service = ConversationService(
        repository,
        FakeCodexClient(),
        workspace_manager=manager,
    )

    created = service.create_conversation()
    workspace = Path(str(created["workspace"]))
    conversation = repository.get_conversation(str(created["id"]))

    assert workspace == (tmp_path / "workspace" / "sessions" / created["id"])
    assert workspace.is_dir()
    assert (workspace / "README.md").is_file()
    assert (manager.shared_root / "playbooks" / "multimodal.md").is_file()
    assert conversation is not None
    assert conversation.workspace_path == str(workspace)
    assert conversation.tool_runtime_version == TOOL_RUNTIME_VERSION
    database.close()


def test_codex_thread_uses_session_cwd_and_shared_root(tmp_path) -> None:
    client = CodexAppServerClient(
        binary=Path("codex.exe"),
        workspace=tmp_path / "workspace",
        protocol_log=tmp_path / "protocol.log",
        protocol_logging_enabled=False,
    )
    session_dir = tmp_path / "workspace" / "sessions" / "session-1"
    shared_dir = tmp_path / "workspace" / "shared"
    captured = {}

    async def fake_request(method, params=None, timeout=30):
        captured["method"] = method
        captured["params"] = params or {}
        return {"thread": {"id": "thread-1"}}

    client.request = fake_request  # type: ignore[method-assign]
    thread_id = asyncio.run(
        client.create_thread(
            cwd=session_dir,
            shared_roots=[shared_dir],
        )
    )

    assert thread_id == "thread-1"
    assert captured["method"] == "thread/start"
    assert captured["params"]["cwd"] == str(session_dir.resolve())
    assert captured["params"]["runtimeWorkspaceRoots"] == [
        str(session_dir.resolve()),
        str(shared_dir.resolve()),
    ]
