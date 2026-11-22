"""Narrow asyncio compatibility workarounds for the local Windows runtime."""

from __future__ import annotations

import asyncio
import os
from typing import Any

_CONNECTION_LOST_CALLBACK = "_call_connection_lost"
_WINDOWS_CONNECTION_RESET = 10054


def _is_expected_windows_connection_reset(context: dict[str, Any]) -> bool:
    """Recognize the harmless Proactor close error caused by a client abort."""

    if os.name != "nt":
        return False
    exception = context.get("exception")
    if not isinstance(exception, ConnectionResetError):
        return False
    winerror = getattr(exception, "winerror", None)
    if winerror is None and exception.args and isinstance(exception.args[0], int):
        winerror = exception.args[0]
    if winerror != _WINDOWS_CONNECTION_RESET:
        return False
    return _CONNECTION_LOST_CALLBACK in repr(context.get("handle"))


def install_windows_connection_reset_filter(
    loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Suppress only client-aborted Proactor close callbacks.

    Video range requests are routinely canceled when the browser seeks, changes
    media, or unmounts a player. Windows Proactor then reports WinError 10054
    from ``_call_connection_lost`` after the HTTP response has already succeeded.
    All unrelated loop errors continue through the previous handler.
    """

    if os.name != "nt":
        return
    current_loop = loop or asyncio.get_running_loop()
    previous = current_loop.get_exception_handler()
    if getattr(previous, "_mivoai_reset_filter", False):
        return

    def filtered_handler(
        active_loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        if _is_expected_windows_connection_reset(context):
            return
        if previous is not None:
            previous(active_loop, context)
            return
        active_loop.default_exception_handler(context)

    filtered_handler._mivoai_reset_filter = True  # type: ignore[attr-defined]
    current_loop.set_exception_handler(filtered_handler)
