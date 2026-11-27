"""Refresh inherited Windows user environment values for child processes."""

from __future__ import annotations

import os
from collections.abc import Iterable, MutableMapping


def merge_registered_environment(
    values: Iterable[tuple[str, str]],
    environ: MutableMapping[str, str] | None = None,
    *,
    overwrite: bool = False,
) -> int:
    """Merge registered values without clobbering process-specific settings."""

    target = environ if environ is not None else os.environ
    changed = 0
    for name, value in values:
        if not name:
            continue
        if not overwrite and target.get(name):
            continue
        target[name] = value
        changed += 1
    return changed


def refresh_windows_user_environment(
    environ: MutableMapping[str, str] | None = None,
) -> int:
    """Load variables added to the Windows user environment after API startup.

    ccswitch may update API keys in the user environment while MivoAi is
    already running. Existing processes do not receive those registry changes,
    so refresh missing values immediately before starting Codex.
    """

    if os.name != "nt":
        return 0
    import winreg

    values: list[tuple[str, str]] = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            index = 0
            while True:
                try:
                    name, raw_value, value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                if value_type not in {winreg.REG_SZ, winreg.REG_EXPAND_SZ}:
                    continue
                if not isinstance(raw_value, str):
                    continue
                value = (
                    winreg.ExpandEnvironmentStrings(raw_value)
                    if value_type == winreg.REG_EXPAND_SZ
                    else raw_value
                )
                values.append((name, value))
    except OSError:
        return 0
    return merge_registered_environment(values, environ)
