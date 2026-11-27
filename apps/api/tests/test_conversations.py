import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.adapters.persistence.database import Database
from app.adapters.persistence.sqlite.conversations import (
    ConversationRepository,
)
from app.main import create_app
from app.modules.conversations.application import (
    derive_conversation_title,
    request_turn_interrupt,
    visible_user_message,
)
from app.modules.conversations.runtime import ActiveTurn
from app.shared.errors import AppServerError
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
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"message": "hello", "clientMessageId": "restart-1"},
        )

    second_app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(second_app) as client:
        assert client.get("/api/conversations").json()[0]["id"] == conversation_id


def test_startup_recovers_interrupted_streaming_message(tmp_path) -> None:
    database_path = tmp_path / "interrupted.db"
    database = Database(database_path)
    repository = ConversationRepository(database)
    conversation = repository.create_conversation(title="中断恢复")
    repository.attach_thread(
        conversation.id,
        "interrupted-thread",
        "中断恢复",
    )
    turn = repository.create_turn_with_messages(
        conversation.id,
        "client-interrupted",
        "继续生成",
    )
    repository.start_submission("client-interrupted", conversation.id)
    repository.append_assistant_content(
        turn.assistant_message_id,
        "已经生成了一部分内容。",
    )
    database.close()

    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        health = client.get("/api/status").json()
        history = client.get(
            f"/api/conversations/{conversation.id}/messages"
        ).json()
        conversation_summary = client.get("/api/conversations").json()[0]

    assert health["recoveredConversationTurns"] == 1
    assert history["active"] is False
    assert history["messages"][-1]["status"] == "interrupted"
    assert "服务重启中断" in history["messages"][-1]["content"]
    assert conversation_summary["status"] == "idle"


def test_conversation_persists_drama_scope_context(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "context.db")
    with TestClient(app) as client:
        created = client.post(
            "/api/conversations",
            json={
                "projectId": "drama-1",
                "episodeId": "episode-3",
                "scope": "episode",
            },
        ).json()
        assert created["projectId"] == "drama-1"
        assert created["episodeId"] == "episode-3"
        assert created["scope"] == "episode"

        client.post(
            f"/api/conversations/{created['id']}/messages",
            json={"message": "检查分镜", "clientMessageId": "scope-1"},
        )
        listed = client.get("/api/conversations").json()[0]

    assert listed["projectId"] == "drama-1"
    assert listed["episodeId"] == "episode-3"
    assert listed["scope"] == "episode"


def test_recent_conversations_are_threads_not_turns(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "threads.db")
    with TestClient(app) as client:
        empty_id = client.post("/api/conversations").json()["id"]
        conversation_id = client.post("/api/conversations").json()["id"]

        for index in range(2):
            response = client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={
                    "message": f"第 {index + 1} 轮",
                    "clientMessageId": f"turn-{index}",
                },
            )
            assert response.status_code == 200

        conversations = client.get("/api/conversations").json()

    assert all(item["id"] != empty_id for item in conversations)
    assert len(conversations) == 1
    assert conversations[0]["threadId"] == "test-thread"
    assert conversations[0]["messageCount"] == 4


def test_model_runtime_change_creates_a_new_codex_thread(tmp_path) -> None:
    codex = FakeCodexClient()
    app = create_app(codex, database_path=tmp_path / "model-switch.db")
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        first = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"message": "第一模型", "clientMessageId": "model-1"},
        )
        assert first.status_code == 200
        first_thread = client.get("/api/conversations").json()[0]["threadId"]

        codex.runtime_signature_value = "switched-runtime"
        second = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"message": "第二模型", "clientMessageId": "model-2"},
        )
        assert second.status_code == 200
        conversations = client.get("/api/conversations").json()
        history = client.get(
            f"/api/conversations/{conversation_id}/messages"
        ).json()

    assert first_thread == "test-thread"
    assert codex.threads_created == 2
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["threadId"] == "test-thread-2"
    assert [message["content"] for message in history["messages"] if message["role"] == "user"] == [
        "第一模型",
        "第二模型",
    ]


def test_drama_context_produces_clean_conversation_title() -> None:
    message = "\n".join(
            [
                "【短剧工作台上下文】",
                "项目：旧教室的第三排",
                "项目 ID：project-1",
                "当前范围：分集 · 第 3 集 真相浮出",
                "当前阶段：分镜画面（keyframes）",
                "当前分集 ID：episode-3",
                "",
                "用户消息：",
                "检查这一集的分镜缺口。",
            ]
        )
    title = derive_conversation_title(message)

    assert title == "短剧 · 分集 · 第 3 集 真相浮出 · 分镜画面"
    assert "上下文" not in title
    assert "用户消息" not in title
    assert visible_user_message(message) == "检查这一集的分镜缺口。"


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

        async def chat(
            self,
            message,
            thread_id,
            workspace=None,
            *,
            cwd=None,
            shared_roots=None,
        ):
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


def test_websocket_rejects_untrusted_origin_and_sse_remains_available(tmp_path):
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(
            "/api/conversations/unknown/ws", headers={"origin": "https://untrusted.example"}
        ):
            pass
        assert exc.value.code == 1008
        response = client.post(
            "/api/conversations/unknown/messages",
            json={"message": "hello", "clientMessageId": "legacy-sse"},
        )
        assert response.status_code == 404


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
