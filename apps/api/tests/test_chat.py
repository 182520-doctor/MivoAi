from fastapi.testclient import TestClient

from app.main import create_app
from tests.fakes import FakeCodexClient


def test_health_reports_app_server(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app_server"]["authenticated"] is True


def test_legacy_chat_returns_migration_status(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "你好"})
    assert response.status_code == 410


def test_legacy_chat_still_validates_input(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422


def test_unconfigured_video_model_is_rejected_before_task_creation(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "test.db")
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations").json()["id"]
        response = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={
                "message": "请生成视频",
                "clientMessageId": "video-1",
                "providerId": "volcengine",
                "modelId": "volc-seedance-2-5",
            },
        )
        assert response.status_code == 400
