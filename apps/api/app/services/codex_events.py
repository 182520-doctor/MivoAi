"""Accumulate streamed items into separate progress and answer projections.

Codex only exposes public reasoning summaries, not private chain-of-thought.
This normalizer combines those public summaries with a lightweight Chinese
workflow hint so the product can show an understandable "thinking process"
without inventing hidden reasoning.
"""

from typing import Any

from app.models.codex import CodexEvent


class TurnEventNormalizer:
    def __init__(self, turn_id: str, user_message: str = "") -> None:
        self.turn_id = turn_id
        self.items: dict[str, dict[str, Any]] = {}
        self.public_progress_hint = _public_progress_hint(user_message)

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
            target.append(_localize_public_summary(text))
        if self.public_progress_hint:
            reasoning.insert(0, self.public_progress_hint)
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


def _public_progress_hint(user_message: str) -> str:
    """Return a visible workflow note tailored to the user's task."""

    normalized = user_message.lower()
    if any(keyword in user_message for keyword in ("剧本", "导演", "分镜", "短片", "故事")):
        return (
            "导演工作流：正在拆解创意核心、人物关系、情绪弧线、场景结构和剧本输出格式。"
            "如果关键信息缺失，会先提出少量问题；信息足够时会直接给出可执行剧本。"
        )
    if any(keyword in user_message for keyword in ("提示词", "画面", "海报", "镜头")):
        return "创作过程：正在提炼主体、构图、风格、光线、材质和可复用提示词结构。"
    if any(keyword in normalized for keyword in ("plan", "方案")) or "创意" in user_message:
        return "创作过程：正在判断目标、受众、风格方向、执行步骤和可落地输出。"
    return "工作过程：正在理解你的需求，整理目标、约束和合适的回答结构。"


def _localize_public_summary(text: str) -> str:
    """Make short public Codex summaries readable for Chinese users."""

    stripped = text.strip()
    translations = {
        "**Preparing concise warm Chinese reply**": "准备一段简洁、友好的中文回复。",
        "Preparing concise warm Chinese reply": "准备一段简洁、友好的中文回复。",
    }
    return translations.get(stripped, text)
