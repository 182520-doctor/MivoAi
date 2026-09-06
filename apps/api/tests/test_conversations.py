import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.exceptions import AppServerError
from app.main import create_app
from app.models.conversation import ActiveTurn
from app.services.conversation_service import request_turn_interrupt
from tests.fakes import FakeCodexClient


def send_turn(client, conversation_id, payload):
    events = []
    with client.websocket_connect(f"/api/conversations/{conversation_id}/ws") as socket:
        ready = socket.receive_json()
        if ready["type"] == "error":
            return [ready]
        socket.send_json({"type": "message", "payload": payload})
        while True:
            event = socket.receive_json()
            events.append(event)
            if event["type"] in {"done", "error"}:
                break
    return events


def test_duplicate_submission_and_unknown_conversation(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        payload = {"message": "hello", "clientMessageId": "one"}
        assert send_turn(client, conversation_id, payload)[-1]["type"] == "done"
        assert send_turn(client, conversation_id, payload)[-1]["code"] == 409
        assert send_turn(client, "unknown", payload)[-1]["code"] == 404
        assert client.get("/api/conversations/not-mine/messages").status_code == 404
        assert send_turn(
            client, conversation_id, {"message": "  ", "clientMessageId": "two"}
        )[-1]["code"] == 422
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
        events = send_turn(
            client, conversation_id,
            {"message": "## 标题\n\n| A | B |\n|---|---|", "clientMessageId": "md-1"},
        )
        assert events[-1]["type"] == "done"

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


@pytest.mark.parametrize("disconnect", [False, True])
def test_websocket_interrupt_and_disconnect_release_turn(tmp_path, disconnect):
    class WaitingClient(FakeCodexClient):
        def __init__(self):
            super().__init__()
            self.interrupted = threading.Event()

        async def chat(self, message, thread_id):
            yield {"type": "meta", "threadId": thread_id, "turnId": "waiting"}
            yield {"type": "output", "content": "", "reasoning": "Working"}
            await asyncio.Event().wait()

        async def request(self, method, params=None, timeout=30):
            if method == "turn/interrupt":
                self.interrupted.set()
            return {}

    codex = WaitingClient()
    app = create_app(codex, database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["id"]
        with client.websocket_connect(f"/api/conversations/{cid}/ws") as socket:
            assert socket.receive_json()["type"] == "ready"
            socket.send_json({"type": "message", "payload": {
                "message": "hello", "clientMessageId": "waiting"
            }})
            assert socket.receive_json()["type"] == "meta"
            assert socket.receive_json()["reasoning"] == "Working"
            assert send_turn(client, cid, {
                "message": "busy", "clientMessageId": "busy"
            })[-1]["code"] == 409
            if disconnect:
                socket.close()
            else:
                socket.send_json({"type": "interrupt"})
                assert socket.receive_json()["status"] == "interrupted"
            assert codex.interrupted.wait(timeout=2)
        history = client.get(f"/api/conversations/{cid}/messages").json()
        assert history["active"] is False
        assert history["messages"][-1]["reasoning"] == "Working"
        assert history["messages"][-1]["content"] == ""


def test_websocket_rejects_untrusted_origin_and_sse_is_removed(tmp_path):
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(
            "/api/conversations/unknown/ws", headers={"origin": "https://untrusted.example"}
        ):
            pass
        assert exc.value.code == 1008
        assert client.post("/api/conversations/unknown/messages").status_code == 410


def test_one_session_socket_handles_multiple_turns_and_validation_errors(tmp_path):
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["id"]
        with client.websocket_connect(f"/api/conversations/{cid}/ws") as socket:
            assert socket.receive_json() == {"type": "ready", "conversationId": cid}
            socket.send_json({"type": "ping"})
            assert socket.receive_json() == {"type": "pong"}
            socket.send_json({"type": "message", "payload": {"message": ""}})
            assert socket.receive_json()["code"] == 422
            for request_id in ("first", "second"):
                socket.send_json({"type": "message", "payload": {
                    "message": request_id, "clientMessageId": request_id
                }})
                while True:
                    event = socket.receive_json()
                    assert event["clientMessageId"] == request_id
                    assert event["type"] != "error"
                    if event["type"] == "done":
                        break
            socket.send_json({"type": "ping"})
            assert socket.receive_json() == {"type": "pong"}
        history = client.get(f"/api/conversations/{cid}/messages").json()
        assert len(history["messages"]) == 4
