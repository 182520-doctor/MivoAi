"""Repository methods that isolate SQL from conversation business rules."""

from __future__ import annotations

import json
import uuid

from app.db.database import Database
from app.models.conversation import Conversation, ConversationMessage, TurnRecord


class ConversationRepository:
    """Persist session metadata, turns, messages, and idempotent submissions."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _to_conversation(row) -> Conversation:
        return Conversation(
            id=row["id"],
            title=row["title"],
            thread_id=row["codex_thread_id"],
            status=row["status"],
        )

    @staticmethod
    def _to_message(row) -> ConversationMessage:
        return ConversationMessage(
            id=row["id"],
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            role=row["role"],
            content=row["content"],
            status=row["status"],
            reasoning=row["reasoning_text"] or "",
            reasoning_tokens=row["reasoning_tokens"] or 0,
        )

    def list_conversations(self) -> list[Conversation]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, title, codex_thread_id, status
                FROM sessions
                ORDER BY updated_at DESC, rowid DESC
                """
            ).fetchall()
        return [self._to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, title, codex_thread_id, status
                FROM sessions
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return self._to_conversation(row) if row else None

    def create_conversation(self, title: str = "新的创意对话") -> Conversation:
        conversation = Conversation(id=str(uuid.uuid4()), title=title, thread_id=None)
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, title, codex_thread_id, status)
                VALUES (?, ?, NULL, 'idle')
                """,
                (conversation.id, conversation.title),
            )
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, title, thread) VALUES (?, ?, NULL)",
                (conversation.id, conversation.title),
            )
        return conversation

    def attach_thread(
        self, conversation_id: str, thread_id: str, title: str
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET codex_thread_id = ?, title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (thread_id, title, conversation_id),
            )
            connection.execute(
                "UPDATE conversations SET thread = ?, title = ? WHERE id = ?",
                (thread_id, title, conversation_id),
            )

    def list_messages(self, conversation_id: str) -> list[ConversationMessage]:
        """Return chronological local history for one session.

        This method deliberately does not call Codex. SQLite is the product source
        of truth for what the browser shows in the conversation detail view.
        """

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    messages.id,
                    messages.session_id,
                    messages.turn_id,
                    messages.role,
                    messages.content,
                    messages.status,
                    turns.reasoning_text,
                    turns.reasoning_tokens
                FROM messages
                LEFT JOIN turns ON turns.id = messages.turn_id
                WHERE messages.session_id = ?
                ORDER BY messages.created_at ASC, messages.rowid ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [self._to_message(row) for row in rows]

    def create_turn_with_messages(
        self, conversation_id: str, client_message_id: str, user_content: str
    ) -> TurnRecord:
        """Create the local turn, user message, and assistant placeholder atomically."""

        turn = TurnRecord(
            id=str(uuid.uuid4()),
            user_message_id=client_message_id,
            assistant_message_id=str(uuid.uuid4()),
        )
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO turns (id, session_id, status)
                VALUES (?, ?, 'running')
                """,
                (turn.id, conversation_id),
            )
            connection.execute(
                """
                INSERT INTO messages (id, session_id, turn_id, role, content, status)
                VALUES (?, ?, ?, 'user', ?, 'done')
                """,
                (turn.user_message_id, conversation_id, turn.id, user_content),
            )
            connection.execute(
                """
                INSERT INTO messages (id, session_id, turn_id, role, content, status)
                VALUES (?, ?, ?, 'assistant', '', 'streaming')
                """,
                (turn.assistant_message_id, conversation_id, turn.id),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )
        return turn

    def create_generation_task(
        self,
        *,
        session_id: str,
        turn_id: str,
        user_id: str,
        provider_id: str,
        model_id: str,
        prompt: str,
        original_request: dict[str, object],
        normalized_request: dict[str, object],
        client_request_id: str,
        task_type: str = "text",
        status: str = "running",
    ) -> str:
        """Create the canonical audit record before an external request is sent."""

        task_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO generation_tasks
                    (id, request_id, session_id, turn_id, user_id, provider_id, model_id,
                    task_type, prompt, original_request_json, normalized_request_json,
                     status, client_request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task_id,
                    session_id,
                    turn_id,
                    user_id,
                    provider_id,
                    model_id,
                    task_type,
                    prompt,
                    json.dumps(original_request, ensure_ascii=False),
                    json.dumps(normalized_request, ensure_ascii=False),
                    status,
                    client_request_id,
                ),
            )
        return task_id

    def update_generation_task_status(
        self,
        task_id: str,
        *,
        status: str,
        progress: int | None = None,
        provider_task_id: str | None = None,
        response: dict[str, object] | None = None,
        error_code: str | None = None,
        error: str | None = None,
        completed: bool = False,
    ) -> None:
        """Update a task and append an auditable state transition event."""

        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?, progress = COALESCE(?, progress),
                    provider_task_id = COALESCE(?, provider_task_id),
                    provider_response_json = COALESCE(?, provider_response_json),
                    error_code = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = ?
                """,
                (
                    status,
                    progress,
                    provider_task_id,
                    json.dumps(response, ensure_ascii=False) if response is not None else None,
                    error_code,
                    error,
                    int(completed),
                    task_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    status,
                    json.dumps(
                        {"progress": progress, "error": error}, ensure_ascii=False
                    ),
                ),
            )

    def create_asset(
        self,
        *,
        session_id: str | None,
        task_id: str,
        asset_type: str,
        source: str,
        local_path: str | None,
        remote_url: str | None,
        mime_type: str | None,
        size: int | None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        asset_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO assets
                    (id, session_id, task_id, type, source, local_path, remote_url,
                     mime_type, size, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    session_id,
                    task_id,
                    asset_type,
                    source,
                    local_path,
                    remote_url,
                    mime_type,
                    size,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return asset_id

    def set_generation_task_assets(self, task_id: str, asset_ids: list[str]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET result_asset_ids_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(asset_ids, ensure_ascii=False), task_id),
            )

    def get_generation_task(self, task_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM generation_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in (
            "original_request_json",
            "normalized_request_json",
            "provider_request_json",
            "provider_response_json",
            "result_asset_ids_json",
        ):
            raw = result.get(key)
            fallback = "[]" if "asset" in key else "{}"
            result[key.removesuffix("_json")] = json.loads(raw or fallback)
        return result

    def get_asset(self, asset_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def update_generation_task_request(
        self, task_id: str, provider_request: dict[str, object]
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET provider_request_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(provider_request, ensure_ascii=False), task_id),
            )

    def finish_generation_task(
        self,
        task_id: str,
        *,
        status: str,
        response: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?, provider_response_json = ?, error_message = ?,
                    updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(response or {}, ensure_ascii=False), error, task_id),
            )

    def set_codex_turn(self, local_turn_id: str, codex_turn_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET codex_turn_id = ? WHERE id = ?",
                (codex_turn_id, local_turn_id),
            )

    def append_assistant_content(self, message_id: str, delta: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = content || ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (delta, message_id),
            )

    def replace_assistant_content(self, message_id: str, content: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content, message_id),
            )

    def append_reasoning(self, turn_id: str, delta: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_text = reasoning_text || ? WHERE id = ?",
                (delta, turn_id),
            )

    def replace_reasoning(self, turn_id: str, text: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_text = ? WHERE id = ?",
                (text, turn_id),
            )

    def update_reasoning_tokens(self, turn_id: str, tokens: int) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_tokens = ? WHERE id = ?",
                (tokens, turn_id),
            )

    def finish_turn(
        self,
        conversation_id: str,
        turn_id: str,
        assistant_message_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        message_status = "error" if error else "done"
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE turns
                SET status = ?, error = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error, turn_id),
            )
            connection.execute(
                """
                UPDATE messages
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (message_status, assistant_message_id),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'idle', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )

    def submission_exists(self, client_message_id: str) -> bool:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT 1 FROM submissions WHERE id = ?", (client_message_id,)
            ).fetchone()
        return row is not None

    def start_submission(self, client_message_id: str, conversation_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO submissions (id, conversation, session_id, status)
                VALUES (?, ?, ?, ?)
                """,
                (client_message_id, conversation_id, conversation_id, "started"),
            )

    def finish_submission(self, client_message_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE submissions
                SET status = 'finished', finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (client_message_id,),
            )
