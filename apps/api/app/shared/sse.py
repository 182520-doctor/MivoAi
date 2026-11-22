"""Server-Sent Events serialization used by streaming HTTP responses."""

import json

from app.contexts.conversations.events import CodexEvent


def encode_sse(event: CodexEvent) -> str:
    """Serialize one normalized event using the SSE data-frame format."""

    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
