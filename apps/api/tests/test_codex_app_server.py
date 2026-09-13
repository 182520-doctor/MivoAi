import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.codex_app_server import (
    CodexAppServerClient,
    _subprocess_startup_options,
)


def test_subprocess_startup_hides_windows_console(monkeypatch) -> None:
    monkeypatch.setattr("app.services.codex_app_server.os.name", "nt")
    monkeypatch.setattr(
        "app.services.codex_app_server.subprocess.CREATE_NO_WINDOW",
        0x08000000,
        raising=False,
    )

    assert _subprocess_startup_options() == {"creationflags": 0x08000000}


def test_subprocess_startup_options_are_empty_off_windows(monkeypatch) -> None:
    monkeypatch.setattr("app.services.codex_app_server.os.name", "posix")

    assert _subprocess_startup_options() == {}


@pytest.mark.parametrize(
    ("account_result", "authenticated", "account_authenticated", "requires_auth"),
    [
        ({"account": None, "requiresOpenaiAuth": False}, True, False, False),
        ({"account": None, "requiresOpenaiAuth": True}, False, False, True),
        ({"account": {"type": "apiKey"}, "requiresOpenaiAuth": True}, True, True, True),
        ({"account": None}, False, False, None),
    ],
)
def test_start_reports_provider_authentication_requirements(
    monkeypatch, tmp_path, account_result, authenticated, account_authenticated, requires_auth
) -> None:
    binary = tmp_path / "codex.exe"
    binary.touch()
    (tmp_path / "codex-code-mode-host").touch()
    client = CodexAppServerClient(
        binary, tmp_path / "workspace", tmp_path / "protocol.log", protocol_logging_enabled=False
    )
    process = MagicMock(returncode=None)
    process.wait = AsyncMock()
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr("app.services.codex_app_server.asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr(client, "_read_stdout", AsyncMock())
    monkeypatch.setattr(client, "_read_stderr", AsyncMock())
    monkeypatch.setattr(client, "notify", AsyncMock())
    request = AsyncMock(side_effect=[{"userAgent": "codex-test"}, account_result])
    monkeypatch.setattr(client, "request", request)

    async def run() -> None:
        assert client.status()["authenticated"] is False
        assert client.status()["requiresOpenaiAuth"] is None
        await client.start()
        try:
            status = client.status()
            assert status["running"] is True
            assert status["authenticated"] is authenticated
            assert status["accountAuthenticated"] is account_authenticated
            assert status["requiresOpenaiAuth"] is requires_auth
            request.assert_any_await("account/read", {"refreshToken": False}, timeout=20)
            assert spawn.call_args.kwargs.items() >= _subprocess_startup_options().items()
        finally:
            await client.stop()
        assert client.status()["running"] is False
        assert client.status()["authenticated"] is False
        assert client.status()["requiresOpenaiAuth"] is None

    asyncio.run(run())


def test_create_thread_is_ephemeral(monkeypatch, tmp_path) -> None:
    client = CodexAppServerClient(
        tmp_path / "codex",
        tmp_path / "workspace",
        tmp_path / "protocol.log",
        protocol_logging_enabled=False,
    )
    request = AsyncMock(return_value={"thread": {"id": "web-thread"}})
    monkeypatch.setattr(client, "request", request)

    thread_id = asyncio.run(client.create_thread(tmp_path / "project"))

    assert thread_id == "web-thread"
    params = request.await_args.args[1]
    assert params["ephemeral"] is True
    assert params["cwd"] == str(tmp_path / "project")


def test_chat_replaces_thread_not_loaded_after_restart(monkeypatch, tmp_path) -> None:
    client = CodexAppServerClient(
        tmp_path / "codex",
        tmp_path / "workspace",
        tmp_path / "protocol.log",
        protocol_logging_enabled=False,
    )
    monkeypatch.setattr(client, "start", AsyncMock())
    monkeypatch.setattr(client, "create_thread", AsyncMock(return_value="fresh-thread"))
    request = AsyncMock(return_value={"turn": {"id": "turn-1"}})
    monkeypatch.setattr(client, "request", request)

    async def run() -> None:
        iterator = client.chat("hello", "stale-thread", tmp_path / "project")
        event = await anext(iterator)
        assert event["threadId"] == "fresh-thread"
        await iterator.aclose()

    asyncio.run(run())
    client.create_thread.assert_awaited_once_with(tmp_path / "project")
    assert request.await_args.args[0] == "turn/start"
    params = request.await_args.args[1]
    assert params["cwd"] == str((tmp_path / "project").resolve())
    assert params["sandboxPolicy"] == {
        "type": "workspaceWrite",
        "writableRoots": [str((tmp_path / "project").resolve())],
        "networkAccess": False,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def test_start_fails_with_actionable_error_when_host_is_missing(tmp_path) -> None:
    binary = tmp_path / "codex"
    binary.touch()
    client = CodexAppServerClient(
        binary,
        tmp_path / "workspace",
        tmp_path / "protocol.log",
        protocol_logging_enabled=False,
    )

    with pytest.raises(Exception, match="codex-code-mode-host"):
        asyncio.run(client.start())
