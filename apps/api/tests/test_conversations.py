import asyncio

from fastapi.testclient import TestClient

from app.contexts.conversations.application import (
    derive_conversation_title,
    request_turn_interrupt,
    visible_user_message,
)
from app.contexts.conversations.infrastructure.repository import (
    ConversationRepository,
)
from app.contexts.conversations.runtime import ActiveTurn
from app.infrastructure.persistence.database import Database
from app.main import create_app
from app.shared.errors import AppServerError
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
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["threadId"] == "test-thread"
    assert conversations[0]["messageCount"] == 4


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
