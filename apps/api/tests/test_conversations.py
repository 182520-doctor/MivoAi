import asyncio

from fastapi.testclient import TestClient

from app.core.exceptions import AppServerError
from app.main import create_app
from app.models.conversation import ActiveTurn
from app.services.conversation_service import request_turn_interrupt
from tests.fakes import FakeCodexClient


def test_duplicate_submission_and_unknown_conversation(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        payload = {"message": "hello", "clientMessageId": "one"}
        assert client.post(
            f"/api/conversations/{conversation_id}/messages", json=payload
        ).status_code == 200
        assert client.post(
            f"/api/conversations/{conversation_id}/messages", json=payload
        ).status_code == 409
        assert client.get("/api/conversations/not-mine/messages").status_code == 404
        assert client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"message": "  ", "clientMessageId": "two"},
        ).status_code == 422
        assert client.get("/api/conversations").json()[0]["id"] == conversation_id


def test_conversation_index_survives_application_restart(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    first_app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(first_app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]

    second_app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(second_app) as client:
        assert client.get("/api/conversations").json()[0]["id"] == conversation_id


def test_history_comes_from_sqlite_not_codex_turns(tmp_path) -> None:
    class NoHistoryClient(FakeCodexClient):
        async def request(self, method, params=None, timeout=30):
            if method == "thread/turns/list":
                raise AssertionError("history must not be loaded from Codex")
            return await super().request(method, params, timeout)

    app = create_app(NoHistoryClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"message": "## 标题\n\n| A | B |\n|---|---|", "clientMessageId": "md-1"},
        )
        assert response.status_code == 200

        history = client.get(f"/api/conversations/{conversation_id}/messages").json()

    assert history["cursor"] is None
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["content"] == "## 标题\n\n| A | B |\n|---|---|"
    assert history["messages"][1]["reasoning"] == "先理解用户需求。"
    assert history["messages"][1]["reasoningTokens"] == 12


def test_interrupt_is_idempotent_when_turn_just_finished() -> None:
    class FinishedClient(FakeCodexClient):
        async def request(self, method, params=None, timeout=30):
            if method == "turn/interrupt":
                raise AppServerError("no active turn to interrupt")
            return await super().request(method, params, timeout)

    active_turn = ActiveTurn(
        queue=asyncio.Queue(),
        thread_id="thread-1",
        turn_id="turn-1",
    )
    asyncio.run(request_turn_interrupt(FinishedClient(), active_turn))
    assert active_turn.stop_requested is True
