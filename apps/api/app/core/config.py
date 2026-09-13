"""Typed application configuration loaded from environment variables.

Keeping path and security settings in one immutable object makes startup behavior
explicit and prevents route modules from reaching into the process environment.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings shared by the API, database, and Codex integration."""

    project_root: Path
    codex_binary: Path
    codex_workspace: Path
    database_path: Path
    protocol_log_path: Path
    secret_key_path: Path
    asset_dir: Path
    creative_workspace_dir: Path
    protocol_logging_enabled: bool
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings once at application startup, with local-safe defaults."""

        project_root = Path(__file__).resolve().parents[4]
        return cls(
            project_root=project_root,
            codex_binary=_resolve_codex_binary(project_root),
            codex_workspace=Path(
                os.getenv("CODEX_WORKSPACE", project_root / "runtime/chat")
            ),
            database_path=Path(
                os.getenv(
                    "DATABASE_PATH",
                    project_root / "apps/api/data/conversations.db",
                )
            ),
            protocol_log_path=Path(
                os.getenv(
                    "CODEX_PROTOCOL_LOG_PATH",
                    project_root / "runtime/logs/codex-protocol.log",
                )
            ),
            protocol_logging_enabled=os.getenv("CODEX_PROTOCOL_LOG", "1") != "0",
            secret_key_path=Path(
                os.getenv("ZAOJING_SECRET_KEY_PATH", project_root / "runtime/secrets/master.key")
            ),
            asset_dir=Path(os.getenv("ZAOJING_ASSET_DIR", project_root / "apps/api/data/assets")),
            creative_workspace_dir=Path(
                os.getenv(
                    "ZAOJING_CREATIVE_WORKSPACE_DIR",
                    project_root / "runtime/creative-projects",
                )
            ),
        )


def _resolve_codex_binary(project_root: Path) -> Path:
    configured = os.getenv("CODEX_BINARY")
    if configured:
        configured_path = Path(configured).expanduser()
        resolved = shutil.which(configured)
        return Path(resolved) if resolved else configured_path

    bundled_fallback: Path | None = None
    for candidate in _bundled_codex_candidates(project_root):
        if not candidate.is_file():
            continue
        bundled_fallback = bundled_fallback or candidate
        if _has_code_mode_host(candidate):
            return candidate

    # GUI launchers such as PyCharm often have a minimal PATH. Probe standard
    # application bundle locations so a complete Codex installation is still
    # discovered without machine-specific configuration.
    for candidate in _installed_codex_candidates():
        if candidate.is_file() and _has_code_mode_host(candidate):
            return candidate

    path_fallback: Path | None = None
    for command in _path_codex_commands():
        resolved = shutil.which(command)
        if not resolved:
            continue
        path_candidate = type(project_root)(resolved)
        path_fallback = path_fallback or path_candidate
        if _has_code_mode_host(path_candidate):
            return path_candidate

    if bundled_fallback:
        return bundled_fallback

    if path_fallback:
        return path_fallback

    return _bundled_codex_candidates(project_root)[0]


def _has_code_mode_host(binary: Path) -> bool:
    """Check whether a Codex installation includes its tool execution companion."""

    suffix = ".exe" if os.name == "nt" else ""
    # Preserve the concrete Path flavor in tests that emulate another OS.
    parent = type(binary)(os.path.dirname(str(binary)))
    return (parent / f"codex-code-mode-host{suffix}").is_file()


def _bundled_codex_candidates(project_root: Path) -> tuple[Path, ...]:
    bin_dir = project_root / "vendor" / "codex" / "bin"
    if os.name == "nt":
        names = ("codex-x86_64-pc-windows-msvc.exe", "codex.exe", "codex.cmd")
    elif os.uname().sysname == "Darwin":
        names = ("codex-aarch64-apple-darwin", "codex-x86_64-apple-darwin", "codex")
    else:
        names = ("codex-x86_64-unknown-linux-musl", "codex-x86_64-unknown-linux-gnu", "codex")
    return tuple(bin_dir / name for name in names)


def _installed_codex_candidates() -> tuple[Path, ...]:
    if os.name == "nt":
        return ()
    if os.uname().sysname != "Darwin":
        return ()
    return (
        Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
        Path("/Applications/Codex.app/Contents/Resources/codex"),
    )


def _path_codex_commands() -> tuple[str, ...]:
    if os.name == "nt":
        return ("codex.cmd", "codex.exe", "codex")
    return ("codex",)
