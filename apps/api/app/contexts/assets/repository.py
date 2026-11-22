"""SQLite persistence for media assets."""

from __future__ import annotations

import json
import uuid

from app.infrastructure.persistence.database import Database


class AssetRepository:
    """Store asset metadata separately from generation task state."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        *,
        session_id: str | None,
        task_id: str | None,
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

    def get(self, asset_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ?", (asset_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def list(self, *, limit: int = 200) -> list[dict[str, object]]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM assets
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
        return result

    def summary(self) -> dict[str, int]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT type, COUNT(*) AS count,
                       COALESCE(SUM(size), 0) AS total_size
                FROM assets
                GROUP BY type
                """
            ).fetchall()
        return {
            str(row["type"]): int(row["count"])
            for row in rows
        } | {
            "totalSize": sum(int(row["total_size"] or 0) for row in rows)
        }
