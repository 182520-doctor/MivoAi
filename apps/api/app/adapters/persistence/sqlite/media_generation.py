"""SQLite repository for the media generation task aggregate."""

from __future__ import annotations

import json
import uuid

from app.adapters.persistence.database import Database


class GenerationTaskRepository:
    """Persist task lifecycle and append task state events."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        *,
        session_id: str | None,
        turn_id: str | None,
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

    def update_status(
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
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?, progress = COALESCE(?, progress),
                    provider_task_id = COALESCE(?, provider_task_id),
                    provider_response_json = COALESCE(?, provider_response_json),
                    error_code = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE
                        WHEN ? THEN CURRENT_TIMESTAMP
                        WHEN ? IN ('succeeded', 'failed', 'canceled')
                            THEN completed_at
                        ELSE NULL
                    END
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
                    status,
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
                    json.dumps({"progress": progress, "error": error}, ensure_ascii=False),
                ),
            )

    def set_assets(self, task_id: str, asset_ids: list[str]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET result_asset_ids_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(asset_ids, ensure_ascii=False), task_id),
            )

    def get(self, task_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT t.*, m.name AS model_name, p.name AS provider_name
                FROM generation_tasks t
                LEFT JOIN models m ON m.id = t.model_id
                LEFT JOIN model_providers p ON p.id = t.provider_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return _decode_task_row(row)

    def list(
        self,
        *,
        limit: int = 100,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        values: list[object] = []
        if task_type:
            clauses.append("t.task_type = ?")
            values.append(task_type)
        if status:
            clauses.append("t.status = ?")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 200)))
        with self._database.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT t.*, m.name AS model_name, p.name AS provider_name
                FROM generation_tasks t
                LEFT JOIN models m ON m.id = t.model_id
                LEFT JOIN model_providers p ON p.id = t.provider_id
                {where}
                ORDER BY t.created_at DESC, t.rowid DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [_decode_task_row(row) for row in rows]

    def summary(self) -> dict[str, int]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM generation_tasks
                GROUP BY status
                """
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def recover_interrupted(self) -> int:
        """Fail tasks that cannot be safely reconnected after a restart."""

        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks
                SET status = 'failed', error_code = 'interrupted',
                    error_message = '服务重启，任务执行已中断，请重新提交',
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('pending', 'queued', 'running')
                  AND NOT (
                      provider_task_id IS NOT NULL
                      AND provider_task_id != ''
                      AND task_type IN ('video_generation', 'video_processing')
                  )
                """
            )
            return int(cursor.rowcount)

    def recoverable_tasks(self) -> list[dict[str, object]]:
        """Return async video tasks whose provider handle can be re-polled."""

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT t.*, m.name AS model_name, p.name AS provider_name
                FROM generation_tasks t
                LEFT JOIN models m ON m.id = t.model_id
                LEFT JOIN model_providers p ON p.id = t.provider_id
                WHERE t.status IN ('pending', 'queued', 'running')
                  AND t.provider_task_id IS NOT NULL
                  AND t.provider_task_id != ''
                  AND t.task_type IN ('video_generation', 'video_processing')
                ORDER BY t.created_at ASC, t.rowid ASC
                """
            ).fetchall()
        return [_decode_task_row(row) for row in rows]

    def update_request(self, task_id: str, provider_request: dict[str, object]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET provider_request_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(provider_request, ensure_ascii=False), task_id),
            )

    def finish(
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


def _decode_task_row(row) -> dict[str, object]:
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
