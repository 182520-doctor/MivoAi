"""Small SQLite connection wrapper with explicit schema initialization."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock


class Database:
    """Own the process-local SQLite connection and serialize write transactions.

    FastAPI can execute requests concurrently. SQLite accepts one writer at a time,
    so the re-entrant lock keeps multi-statement repository operations atomic while
    preserving the existing lightweight local database.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self.transaction() as connection:
            connection.executescript(
                """
                -- sessions 是造境自己的业务会话表。codex_thread_id 只是外部
                -- App Server 的关联 ID，页面历史永远以本地 SQLite 为准。
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    codex_thread_id TEXT,
                    status TEXT NOT NULL DEFAULT 'idle',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                -- conversations 是早期版本的兼容表。保留它，方便旧数据迁移
                -- 和旧测试继续工作，但新的业务读写都走 sessions/messages/turns。
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    thread TEXT
                );

                -- turns 表记录一次用户提交触发的 Agent 回合，包括 Codex turn ID、
                -- 思考文本、思考 token、最终状态和错误信息。
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    codex_turn_id TEXT,
                    status TEXT NOT NULL,
                    reasoning_text TEXT NOT NULL DEFAULT '',
                    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                -- messages 是页面历史的唯一来源。用户消息和助手结果都落这里，
                -- 前端刷新后直接读本表，不再回查 Codex 的本地历史。
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'done',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    conversation TEXT,
                    session_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS model_providers (
                    id TEXT PRIMARY KEY,
                    adapter_key TEXT NOT NULL,
                    auth_mode TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'builtin',
                    base_url TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS provider_credentials (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    secret_source TEXT NOT NULL DEFAULT 'encrypted',
                    encrypted_secret TEXT,
                    secret_ref TEXT,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_verified_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(provider_id) REFERENCES model_providers(id)
                );

                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    model_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    execution_mode TEXT NOT NULL DEFAULT 'sync',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    integration_status TEXT NOT NULL DEFAULT 'planned',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider_id, model_key),
                    FOREIGN KEY(provider_id) REFERENCES model_providers(id)
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    default_text_model_id TEXT,
                    default_image_model_id TEXT,
                    default_video_model_id TEXT,
                    agent_image_enabled INTEGER NOT NULL DEFAULT 0,
                    agent_video_enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS generation_tasks (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    session_id TEXT,
                    turn_id TEXT,
                    user_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    prompt TEXT NOT NULL DEFAULT '',
                    original_request_json TEXT NOT NULL,
                    normalized_request_json TEXT NOT NULL,
                    provider_request_json TEXT,
                    provider_response_json TEXT,
                    status TEXT NOT NULL,
                    progress INTEGER,
                    provider_task_id TEXT,
                    client_request_id TEXT UNIQUE,
                    result_asset_ids_json TEXT NOT NULL DEFAULT '[]',
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(turn_id) REFERENCES turns(id),
                    FOREIGN KEY(provider_id) REFERENCES model_providers(id),
                    FOREIGN KEY(model_id) REFERENCES models(id)
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(task_id) REFERENCES generation_tasks(id)
                );

                -- assets 是所有上传、生成和远程转存素材的统一索引。
                -- 前端展示时优先使用 local_path，remote_url 仅作为供应商审计信息。
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    task_id TEXT,
                    type TEXT NOT NULL CHECK(type IN ('image', 'video', 'audio', 'file')),
                    source TEXT NOT NULL CHECK(source IN ('upload', 'generated', 'remote')),
                    local_path TEXT,
                    remote_url TEXT,
                    mime_type TEXT,
                    size INTEGER,
                    width INTEGER,
                    height INTEGER,
                    duration REAL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(task_id) REFERENCES generation_tasks(id)
                );
                """
            )
            self._add_column_if_missing(
                connection, "submissions", "session_id", "TEXT"
            )
            self._add_column_if_missing(
                connection, "submissions", "created_at", "TEXT"
            )
            self._add_column_if_missing(
                connection, "submissions", "finished_at", "TEXT"
            )
            connection.executescript(
                """
                UPDATE submissions
                SET session_id = conversation
                WHERE session_id IS NULL AND conversation IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                    ON sessions(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_turns_session
                    ON turns(session_id, started_at);
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at, id);
                CREATE INDEX IF NOT EXISTS idx_submissions_session
                    ON submissions(session_id);
                CREATE INDEX IF NOT EXISTS idx_models_provider
                    ON models(provider_id, enabled);
                CREATE INDEX IF NOT EXISTS idx_tasks_session
                    ON generation_tasks(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_events_task
                    ON task_events(task_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_assets_session
                    ON assets(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_assets_task
                    ON assets(task_id, created_at);

                INSERT OR IGNORE INTO sessions (id, title, codex_thread_id, status)
                    SELECT id, title, thread, 'idle' FROM conversations;

                INSERT OR IGNORE INTO model_providers
                    (id, adapter_key, auth_mode, name, kind, base_url, enabled)
                VALUES
                    ('codex_local', 'codex_local', 'codex_local', '本地 Codex', 'builtin', NULL, 1),
                    ('volcengine', 'volcengine', 'api_key', '火山方舟', 'builtin',
                     'https://ark.cn-beijing.volces.com/api/v3', 1);

                INSERT OR IGNORE INTO models
                    (id, provider_id, model_key, name, capabilities_json,
                     execution_mode, integration_status)
                VALUES
                    ('codex-local-default', 'codex_local', 'codex-local', '本地 Codex Agent',
                     '["text"]', 'sync', 'ready'),
                    ('volc-doubao-seed-evolving', 'volcengine', 'doubao-seed-evolving',
                     'Doubao Seed Evolving',
                     '["text","multimodal_understanding"]', 'sync', 'ready'),
                    ('volc-doubao-seed-2-1-pro', 'volcengine',
                     'doubao-seed-2-1-pro-260628', 'Doubao Seed 2.1 Pro',
                     '["text","multimodal_understanding"]', 'sync', 'ready'),
                    ('volc-seedance-2-5', 'volcengine', 'doubao-seedance-2-5-260628',
                     'Doubao Seedance 2.5',
                     '["video_generation","video_from_image"]', 'async', 'ready'),
                    ('volc-seedream-5-pro', 'volcengine',
                     'doubao-seedream-5-0-pro-260628', 'Doubao Seedream 5.0 Pro',
                     '["image_generation","image_edit"]', 'sync', 'ready');

                INSERT OR IGNORE INTO user_preferences (user_id) VALUES ('local-user');
                """
            )

    @staticmethod
    def _add_column_if_missing(
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        """Apply lightweight additive migrations for existing local databases."""

        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit successful operations and roll back the whole unit on failure."""

        with self._lock:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        """Release the SQLite file handle during application shutdown."""

        with self._lock:
            self._connection.close()
