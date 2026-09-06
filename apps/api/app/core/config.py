"""Typed application configuration loaded from environment variables.

Keeping path and security settings in one immutable object makes startup behavior
explicit and prevents route modules from reaching into the process environment.
"""

from __future__ import annotations

import os
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
            codex_binary=Path(
                os.getenv(
                    "CODEX_BINARY",
                    project_root / "vendor/codex/bin/codex-aarch64-apple-darwin",
                )
            ),
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
        )
