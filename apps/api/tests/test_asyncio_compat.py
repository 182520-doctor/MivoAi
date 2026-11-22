from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.shared.asyncio_compat import (
    _is_expected_windows_connection_reset,
    install_windows_connection_reset_filter,
)


class FakeHandle:
    def __repr__(self) -> str:
        return "<Handle _ProactorBasePipeTransport._call_connection_lost(None)>"


class FakeLoop:
    def __init__(self) -> None:
        self.handler: Callable[[Any, dict[str, Any]], None] | None = None

    def get_exception_handler(self):
        return None

    def set_exception_handler(self, handler) -> None:
        self.handler = handler

    def default_exception_handler(self, context: dict[str, Any]) -> None:
        raise AssertionError(f"unexpected loop error: {context}")


def test_recognizes_windows_client_abort_during_connection_close(monkeypatch) -> None:
    monkeypatch.setattr("app.shared.asyncio_compat.os.name", "nt")
    context = {
        "handle": FakeHandle(),
        "exception": ConnectionResetError(10054, "connection reset"),
    }

    assert _is_expected_windows_connection_reset(context) is True


def test_does_not_hide_unrelated_loop_errors(monkeypatch) -> None:
    monkeypatch.setattr("app.shared.asyncio_compat.os.name", "nt")
    unrelated = {
        "handle": FakeHandle(),
        "exception": RuntimeError("application failure"),
    }

    assert _is_expected_windows_connection_reset(unrelated) is False


def test_install_wraps_the_existing_exception_handler(monkeypatch) -> None:
    monkeypatch.setattr("app.shared.asyncio_compat.os.name", "nt")
    loop = FakeLoop()
    previous: list[dict[str, Any]] = []

    loop.get_exception_handler = lambda: (
        lambda _loop, context: previous.append(context)
    )
    install_windows_connection_reset_filter(loop)
    assert loop.handler is not None

    loop.handler(
        loop,
        {
            "handle": FakeHandle(),
            "exception": ConnectionResetError(10054, "connection reset"),
        },
    )
    assert previous == []

    unrelated = {"exception": RuntimeError("application failure")}
    loop.handler(loop, unrelated)
    assert previous == [unrelated]
