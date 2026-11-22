from app.services.codex_events import TurnEventNormalizer


def test_commentary_and_final_answer_stream_to_separate_areas():
    normalizer = TurnEventNormalizer("turn")

    def emit(method, **params):
        return normalizer.normalize({"method": method, "params": {"turnId": "turn", **params}})

    emit("item/started", item={"id": "c", "type": "agentMessage", "phase": "commentary"})
    result = emit("item/agentMessage/delta", itemId="c", delta="Checking")
    assert result["content"] == ""
    assert "工作过程" in result["reasoning"]
    assert "Checking" in result["reasoning"]
    emit("item/completed", item={
        "id": "c", "type": "agentMessage", "phase": "commentary", "text": "Checking"
    })
    emit("item/started", item={"id": "r", "type": "reasoning"})
    emit("item/reasoning/textDelta", itemId="r", delta="Raw text")
    emit("item/reasoning/summaryTextDelta", itemId="r", summaryIndex=0, delta="Summary")
    emit("item/started", item={"id": "f", "type": "agentMessage", "phase": "final_answer"})
    result = emit("item/agentMessage/delta", itemId="f", delta="Answer")
    assert result["content"] == "Answer"
    assert "Checking\n\nSummary" in result["reasoning"]
    result = emit("item/completed", item={
        "id": "f", "type": "agentMessage", "phase": "final_answer", "text": "Answer"
    })
    assert result["content"] == "Answer"
    assert "Checking\n\nSummary" in result["reasoning"]


def test_late_phase_moves_provisional_text_without_duplicates():
    normalizer = TurnEventNormalizer("turn")
    result = normalizer.normalize({"method": "item/agentMessage/delta", "params": {
        "turnId": "turn", "itemId": "f", "delta": "Answer"
    }})
    assert result["content"] == ""
    assert "Answer" in result["reasoning"]
    result = normalizer.normalize({"method": "item/completed", "params": {
        "turnId": "turn", "item": {"id": "f", "type": "agentMessage", "text": "Answer"}
    }})
    assert result["content"] == "Answer"
    assert "工作过程" in result["reasoning"]
    assert normalizer.normalize({"method": "turn/completed", "params": {
        "turn": {"id": "other", "status": "completed"}
    }}) is None


def test_script_task_gets_visible_director_progress_and_localized_summary():
    normalizer = TurnEventNormalizer("turn", user_message="帮我写一个短片剧本")

    normalizer.normalize({"method": "item/started", "params": {
        "turnId": "turn", "item": {"id": "r", "type": "reasoning"}
    }})
    result = normalizer.normalize({"method": "item/reasoning/summaryTextDelta", "params": {
        "turnId": "turn",
        "itemId": "r",
        "summaryIndex": 0,
        "delta": "**Preparing concise warm Chinese reply**",
    }})

    assert "导演工作流" in result["reasoning"]
    assert "准备一段简洁、友好的中文回复。" in result["reasoning"]
