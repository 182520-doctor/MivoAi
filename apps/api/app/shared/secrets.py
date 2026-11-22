"""Local secret storage for user-supplied provider API keys.

The MVP keeps the encryption key in a local file or an environment variable.
The database only receives authenticated ciphertext, never the original key.
"""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

from cryptography.fernet import Fernet


class SecretBox:
    """Encrypt and decrypt provider secrets with a stable local master key."""

    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path
        self._fernet = Fernet(self._load_or_create_key())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")

    def _load_or_create_key(self) -> bytes:
        configured = os.getenv("ZAOJING_MASTER_KEY")
        if configured:
            return configured.encode("ascii")
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        if self._key_path.exists():
            return self._key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self._key_path.write_bytes(key + b"\n")
        with suppress(OSError):
            self._key_path.chmod(0o600)
        return key
