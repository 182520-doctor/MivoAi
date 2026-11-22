"""Application commands for media generation use cases."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CreateGenerationCommand:
    provider_id: str
    model_id: str
    task_type: str
    prompt: str
    session_id: str | None
    turn_id: str | None
    input_asset_ids: list[str]
    reference_asset_ids: dict[str, list[str]]
    parameters: dict[str, object]
    client_request_id: str | None
    raw_request: dict[str, object] = field(default_factory=dict)
