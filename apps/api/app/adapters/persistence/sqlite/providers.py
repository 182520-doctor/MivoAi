"""SQLite repository for providers, credentials, and preferences."""

from __future__ import annotations

from app.adapters.persistence.database import Database


class ProviderRepository:
    """Keep provider-catalog SQL isolated from routing policy."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def list_models(self) -> list[dict[str, object]]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT m.*, p.name AS provider_name,
                       CASE
                         WHEN p.adapter_key = 'comfyui' THEN 1
                         WHEN c.enabled = 1 THEN 1
                         ELSE 0
                       END AS configured
                FROM models m
                JOIN model_providers p ON p.id = m.provider_id AND p.enabled = 1
                LEFT JOIN provider_credentials c ON c.provider_id = p.id
                WHERE m.enabled = 1
                ORDER BY p.id, m.created_at, m.id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_credential(
        self,
        *,
        provider_id: str,
        credential_id: str,
        encrypted_secret: str,
        config_json: str,
        updated_at: str,
        name: str,
    ) -> bool:
        with self._database.transaction() as connection:
            provider = connection.execute(
                "SELECT id FROM model_providers WHERE id = ? AND enabled = 1",
                (provider_id,),
            ).fetchone()
            if not provider:
                return False
            connection.execute(
                """
                INSERT INTO provider_credentials
                    (id, provider_id, name, secret_source, encrypted_secret, config_json,
                     enabled, updated_at)
                VALUES (?, ?, ?, 'encrypted', ?, ?, 1, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    name = excluded.name,
                    secret_source = excluded.secret_source,
                    encrypted_secret = excluded.encrypted_secret,
                    config_json = excluded.config_json,
                    enabled = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    credential_id,
                    provider_id,
                    name,
                    encrypted_secret,
                    config_json,
                    updated_at,
                ),
            )
        return True

    def get_preferences(self) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM user_preferences WHERE user_id = 'local-user'"
            ).fetchone()
        return dict(row) if row else None

    def update_preferences(
        self,
        *,
        default_text_model_id: str | None,
        default_image_model_id: str | None,
        default_video_model_id: str | None,
        agent_image_enabled: bool,
        agent_video_enabled: bool,
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE user_preferences
                SET default_text_model_id = ?, default_image_model_id = ?,
                    default_video_model_id = ?, agent_image_enabled = ?,
                    agent_video_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = 'local-user'
                """,
                (
                    default_text_model_id,
                    default_image_model_id,
                    default_video_model_id,
                    int(agent_image_enabled),
                    int(agent_video_enabled),
                ),
            )

    def resolve_text_model(self, requested_model_id: str | None) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            model_id = requested_model_id
            if not model_id:
                row = connection.execute(
                    """
                    SELECT default_text_model_id
                    FROM user_preferences
                    WHERE user_id = 'local-user'
                    """
                ).fetchone()
                model_id = row["default_text_model_id"] if row else None
            row = connection.execute(
                """
                SELECT m.*, p.name AS provider_name, p.adapter_key, p.base_url,
                       c.id AS credential_id, c.encrypted_secret, c.config_json
                FROM models m JOIN model_providers p ON p.id = m.provider_id
                LEFT JOIN provider_credentials c ON c.provider_id = p.id AND c.enabled = 1
                WHERE m.id = ? AND m.enabled = 1
                """,
                (model_id or "codex-local-default",),
            ).fetchone()
        return dict(row) if row else None

    def resolve_media_model(self, model_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT m.*, p.name AS provider_name, p.adapter_key, p.base_url,
                       c.encrypted_secret, c.config_json
                FROM models m JOIN model_providers p ON p.id = m.provider_id
                LEFT JOIN provider_credentials c ON c.provider_id = p.id AND c.enabled = 1
                WHERE m.id = ? AND m.enabled = 1 AND p.enabled = 1
                """,
                (model_id,),
            ).fetchone()
        return dict(row) if row else None
