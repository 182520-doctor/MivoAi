"""Translate Codex thread history items into the browser's message shape."""

from typing import Any


def normalize_history(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten newest-first App Server turns into chronological chat messages."""

    messages: list[dict[str, Any]] = []
    for turn in reversed(turns):
        for item in turn.get("items", []):
            if item.get("type") == "userMessage":
                content = "\n".join(
                    part.get("text", "") for part in item.get("content", [])
                )
                messages.append(
                    {"id": item["id"], "role": "user", "content": content}
                )
            elif item.get("type") == "agentMessage":
                messages.append(
                    {
                        "id": item["id"],
                        "role": "assistant",
                        "content": item.get("text", ""),
                        "status": "done",
                    }
                )
    return messages
