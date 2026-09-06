"""Sanitized logging for the local Codex JSON-RPC protocol stream."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

SENSITIVE_FIELDS = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "email",
    "idtoken",
    "password",
    "refreshtoken",
    "secret",
    "token",
}


def redact_protocol_value(value: Any) -> Any:
    """Recursively replace credential-like values before they reach any handler."""

    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if key.lower().replace("_", "") in SENSITIVE_FIELDS
            else redact_protocol_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_protocol_value(item) for item in value]
    return value


def create_protocol_logger(log_path: Path) -> logging.Logger:
    """Create one console-and-file logger per absolute protocol log path."""

    logger = logging.getLogger(f"zaojing.codex.{log_path}")
    if logger.handlers:
        return logger

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
