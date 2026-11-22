"""Application commands for conversation use cases."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SendMessageCommand:
    """Validated command produced at the HTTP boundary."""

    message: str
    client_message_id: str
    provider_id: str
    model_id: str | None
    raw_request: dict[str, object] = field(default_factory=dict)
