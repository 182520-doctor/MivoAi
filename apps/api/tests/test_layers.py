from app.core.config import _resolve_codex_binary
from app.core.security import is_origin_allowed
from app.db.database import Database
from app.db.repositories import ConversationRepository


def test_repository_persists_conversation_and_submission(tmp_path) -> None:
    database = Database(tmp_path / "repository.db")
    repository = ConversationRepository(database)

    conversation = repository.create_conversation()
    repository.attach_thread(conversation.id, "thread-1", "第一条创意")
    repository.start_submission("message-1", conversation.id)
    turn = repository.create_turn_with_messages(
        conversation.id, "message-1", "请写一个 Markdown 表格"
    )
    repository.append_reasoning(turn.id, "先拆解需求。")
    repository.update_reasoning_tokens(turn.id, 8)
    repository.append_assistant_content(turn.assistant_message_id, "| 项目 | 内容 |\n")
    repository.finish_turn(
        conversation.id,
        turn.id,
        turn.assistant_message_id,
        "completed",
    )
    repository.finish_submission("message-1")

    restored = repository.get_conversation(conversation.id)
    messages = repository.list_messages(conversation.id)

    assert restored is not None
    assert restored.thread_id == "thread-1"
    assert restored.title == "第一条创意"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "请写一个 Markdown 表格"
    assert messages[1].content == "| 项目 | 内容 |\n"
    assert messages[1].reasoning == "先拆解需求。"
    assert messages[1].reasoning_tokens == 8
    assert repository.submission_exists("message-1") is True
    database.close()




def test_origin_policy_allows_local_browser_and_non_browser_clients() -> None:
    allowed = ("http://127.0.0.1:3000",)

    assert is_origin_allowed(None, allowed) is True
    assert is_origin_allowed("http://127.0.0.1:3000", allowed) is True
    assert is_origin_allowed("https://untrusted.example", allowed) is False


def test_codex_binary_uses_explicit_environment_path(monkeypatch, tmp_path) -> None:
    configured = tmp_path / "custom-codex.exe"
    monkeypatch.setenv("CODEX_BINARY", str(configured))
    monkeypatch.setattr("app.core.config.shutil.which", lambda _: None)

    assert _resolve_codex_binary(tmp_path) == configured


def test_codex_binary_prefers_bundled_windows_binary(monkeypatch, tmp_path) -> None:
    binary = tmp_path / "vendor" / "codex" / "bin" / "codex.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    monkeypatch.delenv("CODEX_BINARY", raising=False)
    monkeypatch.setattr("app.core.config.os.name", "nt")
    monkeypatch.setattr("app.core.config.shutil.which", lambda _: None)

    assert _resolve_codex_binary(tmp_path) == binary


def test_codex_binary_falls_back_to_path_command(monkeypatch, tmp_path) -> None:
    path_binary = tmp_path / "codex.cmd"
    monkeypatch.delenv("CODEX_BINARY", raising=False)
    monkeypatch.setattr("app.core.config.os.name", "nt")
    monkeypatch.setattr("app.core.config.shutil.which", lambda _: str(path_binary))

    assert _resolve_codex_binary(tmp_path) == path_binary
