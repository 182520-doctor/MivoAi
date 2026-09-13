"""Accumulate streamed items into separate progress and answer projections."""

from typing import Any

from app.models.codex import CodexEvent


class TurnEventNormalizer:
    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self.items: dict[str, dict[str, Any]] = {}

    def normalize(self, event: dict[str, Any]) -> CodexEvent | None:
        method = event.get("method")
        params = event.get("params", {})
        if params.get("turnId") not in (None, self.turn_id):
            return None
        if method == "turn/completed":
            turn = params.get("turn", {})
            if turn.get("id") not in (None, self.turn_id):
                return None
            if turn.get("status") == "failed":
                return {
                    "type": "error",
                    "message": (turn.get("error") or {}).get("message", "Codex 回复失败"),
                }
            return {"type": "done", "status": turn.get("status", "completed")}
        if method == "thread/tokenUsage/updated":
            usage = params.get("tokenUsage", {}).get("last", {})
            return {"type": "reasoning_usage", "tokens": usage.get("reasoningOutputTokens", 0)}
        if method in {"item/started", "item/completed"}:
            item = params.get("item", {})
            if item.get("type") not in {"agentMessage", "reasoning"}:
                return None
            state = self.items.setdefault(item["id"], {"text": ""})
            state["kind"] = item["type"]
            if item["type"] == "agentMessage":
                if item.get("phase"):
                    state["phase"] = item["phase"]
                elif method == "item/completed":
                    state.setdefault("phase", "final_answer")
                if "text" in item:
                    state["text"] = item["text"]
            else:
                summary = _text(item.get("summary"))
                content = _text(item.get("content"))
                if summary or content:
                    state["text"] = summary or content
                    state.pop("sections", None)
            return self._output()
        if method == "item/agentMessage/delta":
            state = self.items.setdefault(params["itemId"], {"text": ""})
            state["kind"] = "agentMessage"
            state["text"] += params.get("delta", "")
            return self._output()
        if method in {
            "item/reasoning/summaryTextDelta",
            "item/reasoning/textDelta",
            "item/reasoning/delta",
            "item/reasoningSummary/delta",
            "item/agentReasoning/delta",
        }:
            state = self.items.setdefault(params["itemId"], {"text": ""})
            state["kind"] = "reasoning"
            if method in {"item/reasoning/summaryTextDelta", "item/reasoningSummary/delta"}:
                sections = state.setdefault("sections", {})
                index = params.get("summaryIndex", 0)
                sections[index] = sections.get(index, "") + params.get("delta", "")
            else:
                state["text"] += params.get("delta", "")
            return self._output()
        return None

    def _output(self) -> CodexEvent:
        content: list[str] = []
        reasoning: list[str] = []
        for item in self.items.values():
            sections = item.get("sections")
            text = (
                "\n\n".join(sections[index] for index in sorted(sections))
                if sections else item["text"]
            )
            if not text:
                continue
            # Older servers may omit phase until completion. Keep provisional
            # text in progress, then move it atomically into the final answer.
            target = content if item.get("phase") == "final_answer" else reasoning
            target.append(text)
        return {
            "type": "output",
            "content": "\n\n".join(content),
            "reasoning": "\n\n".join(reasoning),
        }


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_text(part) for part in value)))
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("content") or value.get("summary"))
    return ""
