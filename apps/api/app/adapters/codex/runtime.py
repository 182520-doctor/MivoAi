"""Detect Codex configuration changes that require a new App Server process."""

from __future__ import annotations

import hashlib
import os
import tomllib
from contextlib import suppress
from pathlib import Path


def codex_runtime_signature(home: Path | None = None) -> str:
    """Return a secret-free digest of model and provider configuration."""

    codex_home = (
        home
        if home is not None
        else Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex")))
    )
    config_path = codex_home / "config.toml"
    digest = hashlib.sha256()
    config_data = b""
    with suppress(OSError):
        config_data = config_path.read_bytes()
    digest.update(config_data)

    catalog_path: Path | None = None
    if config_data:
        try:
            config = tomllib.loads(config_data.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            config = {}
        configured_catalog = config.get("model_catalog_json")
        if isinstance(configured_catalog, str) and configured_catalog:
            catalog_path = Path(configured_catalog).expanduser()
            if not catalog_path.is_absolute():
                catalog_path = codex_home / catalog_path

    if catalog_path is not None:
        try:
            digest.update(catalog_path.read_bytes())
        except OSError:
            digest.update(b"<missing-catalog>")

    return digest.hexdigest()[:32]
