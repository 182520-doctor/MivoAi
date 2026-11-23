"""SQLite repository for imported ComfyUI workflows."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.adapters.persistence.database import Database
from app.modules.workflows.domain import ComfyWorkflowRecord, ConvertedWorkflow


class ComfyWorkflowRepository:
    """Keep workflow graph snapshots separate from the public model catalog."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def normalize_standard_capabilities(self) -> int:
        """Backfill semantic capabilities for imported deterministic utilities."""

        utilities = {
            "mivo_std_remove_background.json": "image_processing",
            "mivo_std_extract_first_frame.json": "image_processing",
            "mivo_std_extract_last_frame.json": "image_processing",
            "mivo_std_image_upscale.json": "image_processing",
        }
        changed = 0
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, source_filename, capability, model_id
                FROM comfy_workflows
                """
            ).fetchall()
            for row in rows:
                capability = utilities.get(str(row["source_filename"]))
                if not capability or row["capability"] == capability:
                    continue
                connection.execute(
                    """
                    UPDATE comfy_workflows
                    SET capability = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (capability, row["id"]),
                )
                connection.execute(
                    """
                    UPDATE models
                    SET capabilities_json = ?, execution_mode = 'sync',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps([capability]), row["model_id"]),
                )
                changed += 1
        return changed

    def upsert(
        self,
        *,
        source_filename: str,
        name: str,
        converted: ConvertedWorkflow,
    ) -> ComfyWorkflowRecord:
        bindings = converted.bindings.to_dict()
        with self._database.transaction() as connection:
            existing = connection.execute(
                "SELECT id, model_id FROM comfy_workflows WHERE source_filename = ?",
                (source_filename,),
            ).fetchone()
            workflow_id = existing["id"] if existing else str(uuid.uuid4())
            model_id = existing["model_id"] if existing else f"comfy-wf-{uuid.uuid4()}"
            config_json = json.dumps(
                {
                    "kind": "comfy_workflow",
                    "workflowId": workflow_id,
                    "apiGraph": converted.api_graph,
                    "bindings": bindings,
                    "parameters": list(converted.parameter_schema),
                    "outputNodeId": converted.output_node_id,
                },
                ensure_ascii=False,
            )
            connection.execute(
                """
                INSERT INTO models
                    (id, provider_id, model_key, name, capabilities_json,
                     execution_mode, enabled, integration_status, config_json)
                VALUES (?, 'comfyui', ?, ?, ?, ?, 0, 'testing', ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    model_key = excluded.model_key,
                    capabilities_json = excluded.capabilities_json,
                    execution_mode = excluded.execution_mode,
                    enabled = 0,
                    integration_status = 'testing',
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    model_id,
                    f"workflow:{workflow_id}",
                    name,
                    json.dumps([converted.capability]),
                    (
                        "async"
                        if converted.capability
                        in {"video_generation", "video_processing"}
                        else "sync"
                    ),
                    config_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO comfy_workflows
                    (id, source_filename, name, capability, status, api_graph_json,
                     bindings_json, parameter_schema_json, input_catalog_json,
                     topology_json, output_node_id, model_id)
                VALUES (?, ?, ?, ?, 'untested', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_filename) DO UPDATE SET
                    name = excluded.name,
                    capability = excluded.capability,
                    status = 'untested',
                    test_asset_id = NULL,
                    test_message = NULL,
                    last_tested_at = NULL,
                    api_graph_json = excluded.api_graph_json,
                    bindings_json = excluded.bindings_json,
                    parameter_schema_json = excluded.parameter_schema_json,
                    input_catalog_json = excluded.input_catalog_json,
                    topology_json = excluded.topology_json,
                    output_node_id = excluded.output_node_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    workflow_id,
                    source_filename,
                    name,
                    converted.capability,
                    json.dumps(converted.api_graph, ensure_ascii=False),
                    json.dumps(bindings, ensure_ascii=False),
                    json.dumps(
                        [dict(item) for item in converted.parameter_schema],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [dict(item) for item in converted.input_catalog],
                        ensure_ascii=False,
                    ),
                    json.dumps(converted.topology, ensure_ascii=False),
                    converted.output_node_id,
                    model_id,
                ),
            )
        record = self.get(workflow_id)
        if not record:
            raise RuntimeError("工作流保存失败")
        return record

    def get(self, workflow_id: str) -> ComfyWorkflowRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM comfy_workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
        return _record(row)

    def list(self) -> list[ComfyWorkflowRecord]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM comfy_workflows ORDER BY updated_at DESC, rowid DESC"
            ).fetchall()
        return [record for row in rows if (record := _record(row))]

    def set_enabled(self, workflow_id: str, enabled: bool) -> None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT model_id FROM comfy_workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return
            connection.execute(
                """
                UPDATE models SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(enabled), row["model_id"]),
            )
            connection.execute(
                """
                UPDATE comfy_workflows
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("ready" if enabled else "disabled", workflow_id),
            )

    def save_test_result(
        self,
        workflow_id: str,
        *,
        asset_id: str | None,
        message: str,
        success: bool,
    ) -> None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT model_id FROM comfy_workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return
            connection.execute(
                """
                UPDATE comfy_workflows
                SET test_asset_id = ?, test_message = ?, status = ?,
                    last_tested_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    asset_id or None,
                    message,
                    "ready" if success else "failed",
                    workflow_id,
                ),
            )
            connection.execute(
                """
                UPDATE models
                SET enabled = ?, integration_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(success), "ready" if success else "failed", row["model_id"]),
            )

    def update_parameters(
        self, workflow_id: str, parameters: list[dict[str, object]]
    ) -> None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT model_id FROM comfy_workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return
            model = connection.execute(
                "SELECT config_json FROM models WHERE id = ?", (row["model_id"],)
            ).fetchone()
            config = json.loads(model["config_json"] or "{}") if model else {}
            config["parameters"] = parameters
            connection.execute(
                """
                UPDATE comfy_workflows
                SET parameter_schema_json = ?, status = 'untested',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(parameters, ensure_ascii=False), workflow_id),
            )
            connection.execute(
                """
                UPDATE models
                SET config_json = ?, enabled = 0,
                    integration_status = 'testing',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(config, ensure_ascii=False), row["model_id"]),
            )

    def update_input_catalog(
        self,
        workflow_id: str,
        input_catalog: list[dict[str, object]],
        topology: dict[str, Any] | None = None,
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE comfy_workflows
                SET input_catalog_json = ?,
                    topology_json = CASE
                        WHEN ? = '{}' THEN topology_json
                        ELSE ?
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(input_catalog, ensure_ascii=False),
                    json.dumps(topology or {}, ensure_ascii=False),
                    json.dumps(topology or {}, ensure_ascii=False),
                    workflow_id,
                ),
            )

    def delete(self, workflow_id: str) -> bool:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT model_id FROM comfy_workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if not row:
                return False
            model_id = str(row["model_id"])
            connection.execute(
                "DELETE FROM comfy_workflows WHERE id = ?",
                (workflow_id,),
            )
            connection.execute(
                """
                UPDATE user_preferences
                SET default_image_model_id = CASE
                        WHEN default_image_model_id = ? THEN NULL
                        ELSE default_image_model_id
                    END,
                    default_video_model_id = CASE
                        WHEN default_video_model_id = ? THEN NULL
                        ELSE default_video_model_id
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = 'local-user'
                """,
                (model_id, model_id),
            )
            task_count = connection.execute(
                "SELECT COUNT(*) AS count FROM generation_tasks WHERE model_id = ?",
                (model_id,),
            ).fetchone()["count"]
            if task_count:
                connection.execute(
                    """
                    UPDATE models
                    SET enabled = 0, integration_status = 'deleted',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (model_id,),
                )
            else:
                connection.execute(
                    "DELETE FROM models WHERE id = ?",
                    (model_id,),
                )
            return True


def _record(row) -> ComfyWorkflowRecord | None:
    if not row:
        return None
    return ComfyWorkflowRecord(
        id=row["id"],
        source_filename=row["source_filename"],
        name=row["name"],
        capability=row["capability"],
        status=row["status"],
        api_graph=json.loads(row["api_graph_json"]),
        bindings=json.loads(row["bindings_json"]),
        parameter_schema=json.loads(row["parameter_schema_json"] or "[]"),
        input_catalog=json.loads(row["input_catalog_json"] or "[]"),
        topology=json.loads(row["topology_json"] or "{}"),
        output_node_id=row["output_node_id"],
        model_id=row["model_id"],
        test_asset_id=row["test_asset_id"],
        test_message=row["test_message"],
    )
