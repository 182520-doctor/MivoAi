from app.services.codex_events import TurnEventNormalizer


def test_commentary_and_final_answer_stream_to_separate_areas():
    normalizer = TurnEventNormalizer("turn")

    def emit(method, **params):
        return normalizer.normalize({"method": method, "params": {"turnId": "turn", **params}})

    emit("item/started", item={"id": "c", "type": "agentMessage", "phase": "commentary"})
    result = emit("item/agentMessage/delta", itemId="c", delta="Checking")
    assert result == {"type": "output", "content": "", "reasoning": "Checking"}
    emit("item/completed", item={
        "id": "c", "type": "agentMessage", "phase": "commentary", "text": "Checking"
    })
    emit("item/started", item={"id": "r", "type": "reasoning"})
    emit("item/reasoning/textDelta", itemId="r", delta="Raw text")
    emit("item/reasoning/summaryTextDelta", itemId="r", summaryIndex=0, delta="Summary")
    emit("item/started", item={"id": "f", "type": "agentMessage", "phase": "final_answer"})
    result = emit("item/agentMessage/delta", itemId="f", delta="Answer")
    assert result["content"] == "Answer"
    assert result["reasoning"] == "Checking\n\nSummary"
    result = emit("item/completed", item={
        "id": "f", "type": "agentMessage", "phase": "final_answer", "text": "Answer"
    })
    assert result["content"] == "Answer"
    assert result["reasoning"] == "Checking\n\nSummary"


def test_late_phase_moves_provisional_text_without_duplicates():
    normalizer = TurnEventNormalizer("turn")
    result = normalizer.normalize({"method": "item/agentMessage/delta", "params": {
        "turnId": "turn", "itemId": "f", "delta": "Answer"
    }})
    assert result["content"] == ""
    assert result["reasoning"] == "Answer"
    result = normalizer.normalize({"method": "item/completed", "params": {
        "turnId": "turn", "item": {"id": "f", "type": "agentMessage", "text": "Answer"}
    }})
    assert result == {"type": "output", "content": "Answer", "reasoning": ""}
    assert normalizer.normalize({"method": "turn/completed", "params": {
        "turn": {"id": "other", "status": "completed"}
    }}) is None
