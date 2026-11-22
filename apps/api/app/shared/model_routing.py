"""Cross-context value objects for resolved model execution routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class TextModelRoute:
    """Resolved text model plus the runtime that must execute it."""

    provider_id: str
    model_id: str
    runtime: Literal["codex", "http"]
    provider_model: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MediaModelRoute:
    """Resolved media model and credentials needed by an execution adapter."""

    id: str
    provider_id: str
    model_key: str
    base_url: str
    api_key: str
    config: dict[str, Any] = field(default_factory=dict)
