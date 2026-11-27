"""SQLite repository for conversation aggregates and submissions."""

from __future__ import annotations

import uuid

from app.adapters.persistence.database import Database
from app.modules.conversations.domain import (
    TOOL_RUNTIME_VERSION,
    Conversation,
    ConversationMessage,
    TurnRecord,
)


class ConversationRepository:
    """Persist sessions, turns, messages, and idempotent submissions."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _to_conversation(row) -> Conversation:
        return Conversation(
            id=row["id"],
            title=row["title"],
            thread_id=row["codex_thread_id"],
            status=row["status"],
            tool_runtime_version=row["tool_runtime_version"],
            runtime_signature=row["agent_runtime_signature"] or "",
            workspace_path=row["workspace_path"],
            project_id=row["project_id"],
            episode_id=row["episode_id"],
            scope=row["scope"],
            message_count=row["message_count"] or 0,
            last_activity_at=row["last_activity_at"],
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
        """List visible Codex threads rather than every local message turn.

        A local session owns one Codex thread. Older databases may contain more
        than one local row for the same thread, so the newest representative is
        selected and sessions without messages are omitted.
        """

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                WITH thread_rows AS (
                    SELECT
                        sessions.*,
                        sessions.rowid AS session_rowid,
                        (
                            SELECT COUNT(*)
                            FROM messages
                            WHERE messages.session_id = sessions.id
                        ) AS message_count,
                        (
                            SELECT MAX(messages.updated_at)
                            FROM messages
                            WHERE messages.session_id = sessions.id
                        ) AS last_activity_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(
                                sessions.codex_thread_id,
                                sessions.id
                            )
                            ORDER BY sessions.updated_at DESC, sessions.rowid DESC
                        ) AS thread_rank
                    FROM sessions
                    WHERE sessions.codex_thread_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM messages
                        WHERE messages.session_id = sessions.id
                    )
                )
                SELECT id, title, codex_thread_id, status,
                       tool_runtime_version, agent_runtime_signature,
                       workspace_path,
                       project_id, episode_id, scope,
                       message_count, last_activity_at
                FROM thread_rows
                WHERE thread_rank = 1
                ORDER BY
                    COALESCE(last_activity_at, updated_at) DESC,
                    session_rowid DESC
                """
            ).fetchall()
        return [self._to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, title, codex_thread_id, status,
                       tool_runtime_version, agent_runtime_signature,
                       workspace_path,
                       project_id, episode_id, scope,
                       (
                           SELECT COUNT(*)
                           FROM messages
                           WHERE messages.session_id = sessions.id
                       ) AS message_count,
                       (
                           SELECT MAX(messages.updated_at)
                           FROM messages
                           WHERE messages.session_id = sessions.id
                       ) AS last_activity_at
                FROM sessions
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return self._to_conversation(row) if row else None

    def create_conversation(
        self,
        title: str = "新的创意对话",
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        scope: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=title,
            thread_id=None,
            tool_runtime_version=TOOL_RUNTIME_VERSION,
            project_id=project_id,
            episode_id=episode_id,
            scope=scope,
        )
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions
                    (id, title, codex_thread_id, status, tool_runtime_version,
                     workspace_path, project_id, episode_id, scope)
                VALUES (?, ?, NULL, 'idle', ?, NULL, ?, ?, ?)
                """,
                (
                    conversation.id,
                    conversation.title,
                    TOOL_RUNTIME_VERSION,
                    project_id,
                    episode_id,
                    scope,
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, title, thread) VALUES (?, ?, NULL)",
                (conversation.id, conversation.title),
            )
        return conversation

    def attach_thread(
        self,
        conversation_id: str,
        thread_id: str,
        title: str,
        tool_runtime_version: int = 0,
        runtime_signature: str = "",
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET codex_thread_id = ?, title = ?,
                    tool_runtime_version = ?,
                    agent_runtime_signature = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    thread_id,
                    title,
                    tool_runtime_version,
                    runtime_signature,
                    conversation_id,
                ),
            )
            connection.execute(
                "UPDATE conversations SET thread = ?, title = ? WHERE id = ?",
                (thread_id, title, conversation_id),
            )

    def set_workspace(self, conversation_id: str, workspace_path: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET workspace_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (workspace_path, conversation_id),
            )

    def list_messages(self, conversation_id: str) -> list[ConversationMessage]:
        """Return local history; Codex history is never the product source of truth."""

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
                "INSERT INTO turns (id, session_id, status) VALUES (?, ?, 'running')",
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

    def recover_interrupted_turns(self) -> int:
        """Close turns left running by a previous API process.

        A hard restart cannot resume an in-memory Codex SSE stream. Marking the
        persisted placeholder as an error lets the user resend immediately and
        prevents the UI from keeping a permanent "streaming" bubble.
        """

        notice = "回复因服务重启中断，可重新发送或继续提问。"
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM messages
                WHERE role = 'assistant' AND status = 'streaming'
                """
            ).fetchall()
            connection.execute(
                """
                UPDATE messages
                SET content = CASE
                        WHEN trim(content) = '' THEN ?
                        ELSE content || ? || ?
                    END,
                    status = 'interrupted',
                    updated_at = CURRENT_TIMESTAMP
                WHERE role = 'assistant' AND status = 'streaming'
                """,
                (notice, "\n\n", notice),
            )
            connection.execute(
                """
                UPDATE messages
                SET status = 'interrupted',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'error'
                AND content LIKE '%服务重启中断%'
                """
            )
            connection.execute(
                """
                UPDATE turns
                SET status = 'interrupted',
                    error = COALESCE(error, ?),
                    completed_at = CURRENT_TIMESTAMP
                WHERE status = 'running'
                """,
                (notice,),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'idle', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'running'
                """
            )
            connection.execute(
                """
                UPDATE submissions
                SET status = 'interrupted',
                    finished_at = CURRENT_TIMESTAMP
                WHERE status = 'started'
                """
            )
        return len(rows)

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
