"""Provider catalog, credential management, and model selection service."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime

from app.core.exceptions import ProviderConfigurationError
from app.core.secrets import SecretBox
from app.db.database import Database
from app.models.gateway import CredentialUpsert, PreferenceUpdate


class ProviderService:
    """Expose a safe model catalog and keep provider credentials server-side."""

    def __init__(self, database: Database, secret_box: SecretBox) -> None:
        self._database = database
        self._secret_box = secret_box

    def list_models(self) -> list[dict[str, object]]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT m.*, p.name AS provider_name,
                       CASE WHEN c.enabled = 1 THEN 1 ELSE 0 END AS configured
                FROM models m
                JOIN model_providers p ON p.id = m.provider_id AND p.enabled = 1
                LEFT JOIN provider_credentials c ON c.provider_id = p.id
                WHERE m.enabled = 1
                ORDER BY p.id, m.created_at, m.id
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "providerId": row["provider_id"],
                "providerName": row["provider_name"],
                "name": row["name"],
                "modelKey": row["model_key"],
                "capabilities": json.loads(row["capabilities_json"]),
                "executionMode": row["execution_mode"],
                "enabled": bool(row["enabled"]),
                "configured": bool(row["configured"]),
                "integrationStatus": row["integration_status"],
            }
            for row in rows
        ]

    def upsert_credential(self, provider_id: str, payload: CredentialUpsert) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        credential_id = str(uuid.uuid4())
        encrypted = self._secret_box.encrypt(payload.api_key)
        with self._database.transaction() as connection:
            provider = connection.execute(
                "SELECT id FROM model_providers WHERE id = ? AND enabled = 1", (provider_id,)
            ).fetchone()
            if not provider:
                raise ProviderConfigurationError("供应商不存在或已停用")
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
                    f"{provider_id} API Key",
                    encrypted,
                    json.dumps(
                        {"base_url": payload.base_url} if payload.base_url else {},
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
        return {"providerId": provider_id, "configured": True, "updatedAt": now}

    def get_preferences(self) -> dict[str, object]:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM user_preferences WHERE user_id = 'local-user'"
            ).fetchone()
        return {
            "defaultTextModelId": row["default_text_model_id"],
            "defaultImageModelId": row["default_image_model_id"],
            "defaultVideoModelId": row["default_video_model_id"],
            "agentImageEnabled": bool(row["agent_image_enabled"]),
            "agentVideoEnabled": bool(row["agent_video_enabled"]),
        }

    def update_preferences(self, payload: PreferenceUpdate) -> dict[str, object]:
        values = payload.model_dump(by_alias=False)
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE user_preferences
                SET default_text_model_id = ?, default_image_model_id = ?,
                    default_video_model_id = ?, agent_image_enabled = ?,
                    agent_video_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = 'local-user'
                """,
                (values["default_text_model_id"], values["default_image_model_id"],
                 values["default_video_model_id"], int(values["agent_image_enabled"]),
                 int(values["agent_video_enabled"])),
            )
        return self.get_preferences()

    def resolve_text_model(self, requested_model_id: str | None) -> dict[str, object]:
        model_id = requested_model_id
        with self._database.transaction() as connection:
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
        if not row:
            raise ProviderConfigurationError("模型不存在或已停用")
        result = dict(row)
        capabilities = json.loads(str(result["capabilities_json"]))
        if "text" not in capabilities or result["integration_status"] != "ready":
            raise ProviderConfigurationError("当前模型暂不支持已接入的文本对话能力")
        if result.get("encrypted_secret"):
            result["api_key"] = self._secret_box.decrypt(result["encrypted_secret"])
        elif result["provider_id"] == "volcengine":
            result["api_key"] = os.getenv("ZAOJING_VOLCENGINE_API_KEY")
        return result

    def resolve_media_model(self, model_id: str, task_type: str) -> dict[str, object]:
        """Resolve a configured model and enforce its declared capability."""

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
        if not row:
            raise ProviderConfigurationError("模型不存在或已停用")
        result = dict(row)
        capabilities = json.loads(str(result["capabilities_json"]))
        if task_type not in capabilities or result["integration_status"] != "ready":
            raise ProviderConfigurationError("当前模型尚未接通该生成能力")
        if result.get("encrypted_secret"):
            result["api_key"] = self._secret_box.decrypt(result["encrypted_secret"])
        elif result["provider_id"] == "volcengine":
            result["api_key"] = os.getenv("ZAOJING_VOLCENGINE_API_KEY")
        if not result.get("api_key"):
            raise ProviderConfigurationError("尚未配置该供应商 API Key")
        return result
