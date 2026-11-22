import asyncio
import json

from app.contexts.media_generation.application import GenerationService
from app.contexts.media_generation.repository import GenerationTaskRepository
from app.contexts.workflows.application import _workflow_test_values
from app.contexts.workflows.domain import ComfyWorkflowRecord
from app.contexts.workflows.repository import ComfyWorkflowRepository
from app.infrastructure.persistence.database import Database
from app.shared.model_routing import MediaModelRoute


def test_delete_imported_workflow_removes_unused_model(tmp_path) -> None:
    database = Database(tmp_path / "delete.db")
    repository = ComfyWorkflowRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO models
                (id, provider_id, model_key, name, capabilities_json,
                 execution_mode, enabled, integration_status, config_json)
            VALUES ('model-delete', 'comfyui', 'workflow:test', 'Delete me',
                    '["image_generation"]', 'sync', 1, 'ready', '{}')
            """
        )
        connection.execute(
            """
            INSERT INTO comfy_workflows
                (id, source_filename, name, capability, status,
                 api_graph_json, bindings_json, parameter_schema_json,
                 input_catalog_json, topology_json, output_node_id, model_id)
            VALUES ('workflow-delete', 'delete.json', 'Delete me',
                    'image_generation', 'ready', '{}', '{}', '[]', '[]',
                    '{}', '1', 'model-delete')
            """
        )

    assert repository.delete("workflow-delete") is True

    with database.transaction() as connection:
        assert connection.execute(
            "SELECT id FROM models WHERE id = 'model-delete'"
        ).fetchone() is None
    database.close()


def test_normalize_standard_utility_workflow_capabilities(tmp_path) -> None:
    database = Database(tmp_path / "workflow-capabilities.db")
    repository = ComfyWorkflowRepository(database)
    with database.transaction() as connection:
        for suffix, capability in (
            ("remove_background", "image_generation"),
            ("extract_last_frame", "image_generation"),
            ("image_upscale", "image_generation"),
        ):
            model_id = f"model-{suffix}"
            connection.execute(
                """
                INSERT INTO models
                    (id, provider_id, model_key, name, capabilities_json,
                     execution_mode, enabled, integration_status, config_json)
                VALUES (?, 'comfyui', ?, ?, ?, 'sync', 1, 'ready', '{}')
                """,
                (
                    model_id,
                    f"workflow:{suffix}",
                    suffix,
                    json.dumps([capability]),
                ),
            )
            connection.execute(
                """
                INSERT INTO comfy_workflows
                    (id, source_filename, name, capability, status,
                     api_graph_json, bindings_json, parameter_schema_json,
                     input_catalog_json, topology_json, output_node_id, model_id)
                VALUES (?, ?, ?, ?, 'ready', '{}', '{}', '[]', '[]',
                        '{}', '1', ?)
                """,
                (
                    f"workflow-{suffix}",
                    f"mivo_std_{suffix}.json",
                    suffix,
                    capability,
                    model_id,
                ),
            )

    assert repository.normalize_standard_capabilities() == 3

    with database.transaction() as connection:
        workflows = connection.execute(
            "SELECT capability FROM comfy_workflows ORDER BY id"
        ).fetchall()
        models = connection.execute(
            """
            SELECT capabilities_json FROM models
            WHERE id LIKE 'model-%'
            ORDER BY id
            """
        ).fetchall()
    assert {row["capability"] for row in workflows} == {"image_processing"}
    assert {
        item
        for row in models
        for item in json.loads(row["capabilities_json"])
    } == {"image_processing"}
    database.close()


def test_delete_workflow_preserves_model_with_task_history(tmp_path) -> None:
    database = Database(tmp_path / "delete-history.db")
    repository = ComfyWorkflowRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO models
                (id, provider_id, model_key, name, capabilities_json,
                 execution_mode, enabled, integration_status, config_json)
            VALUES ('model-history', 'comfyui', 'workflow:history', 'History',
                    '["image_generation"]', 'sync', 1, 'ready', '{}')
            """
        )
        connection.execute(
            """
            INSERT INTO comfy_workflows
                (id, source_filename, name, capability, status,
                 api_graph_json, bindings_json, parameter_schema_json,
                 input_catalog_json, topology_json, output_node_id, model_id)
            VALUES ('workflow-history', 'history.json', 'History',
                    'image_generation', 'ready', '{}', '{}', '[]', '[]',
                    '{}', '1', 'model-history')
            """
        )
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 original_request_json, normalized_request_json, status)
            VALUES ('task-history', 'request-history', 'local-user', 'comfyui',
                    'model-history', 'image_generation', '{}', '{}', 'succeeded')
            """
        )

    assert repository.delete("workflow-history") is True

    with database.transaction() as connection:
        model = connection.execute(
            """
            SELECT enabled, integration_status FROM models
            WHERE id = 'model-history'
            """
        ).fetchone()
        assert model is not None
        assert model["enabled"] == 0
        assert model["integration_status"] == "deleted"
    database.close()


def test_workflow_test_values_include_saved_dimension_defaults() -> None:
    record = ComfyWorkflowRecord(
        id="workflow-test",
        source_filename="test.json",
        name="Test",
        capability="video_generation",
        status="untested",
        api_graph={},
        bindings={},
        parameter_schema=[
            {
                "key": "width",
                "label": "宽度",
                "type": "integer",
                "required": True,
                "default": None,
                "semanticKey": "width",
            },
            {
                "key": "aspect_ratio",
                "label": "画面比例",
                "type": "string",
                "required": True,
                "default": "16:9",
                "semanticKey": "aspectRatio",
            },
        ],
        input_catalog=[
            {
                "field": "width",
                "fieldLabel": "宽度",
                "default": 1344,
            },
            {
                "field": "megapixels",
                "fieldLabel": "像素",
                "default": 4,
            },
        ],
        topology={},
        output_node_id="1",
        model_id="model-test",
        test_asset_id=None,
        test_message=None,
    )

    values = _workflow_test_values(record, "test prompt")

    assert values["prompt"] == "test prompt"
    assert values["width"] == 1344
    assert values["aspectRatio"] == "16:9"
    assert values["resolution"] == 4


def test_interrupted_tasks_are_failed_on_service_restart(tmp_path) -> None:
    database = Database(tmp_path / "recover.db")
    repository = GenerationTaskRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 original_request_json, normalized_request_json, status)
            VALUES ('task-running', 'request-running', 'local-user',
                    'comfyui', 'comfy-flux-image', 'image_generation',
                    '{}', '{}', 'running')
            """
        )

    assert repository.recover_interrupted() == 1
    task = repository.get("task-running")
    assert task is not None
    assert task["status"] == "failed"
    assert task["error_code"] == "interrupted"
    database.close()


def test_video_task_with_provider_handle_is_recoverable(tmp_path) -> None:
    database = Database(tmp_path / "recover-video.db")
    repository = GenerationTaskRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 original_request_json, normalized_request_json, status,
                 provider_task_id)
            VALUES ('task-video', 'request-video', 'local-user',
                    'comfyui', 'comfy-wan-video', 'video_generation',
                    '{}', '{}', 'running', 'prompt-123')
            """
        )

    recoverable = repository.recoverable_tasks()
    assert [task["id"] for task in recoverable] == ["task-video"]
    assert repository.recover_interrupted() == 0
    task = repository.get("task-video")
    assert task is not None
    assert task["status"] == "running"
    database.close()


class _RecoveryProviders:
    def resolve_media_model(self, provider_id, model_id, task_type):
        return MediaModelRoute(
            id=model_id,
            provider_id=provider_id,
            model_key=f"test:{task_type}",
            base_url="http://127.0.0.1:8000",
            api_key="",
            config={"parameters": []},
        )


class _RecoveryAssets:
    def __init__(self):
        self.imported = []

    async def import_remote(
        self,
        *,
        url,
        session_id,
        task_id,
        asset_type,
        filename,
        metadata=None,
    ):
        self.imported.append(
            {
                "url": url,
                "taskId": task_id,
                "assetType": asset_type,
                "filename": filename,
                "metadata": metadata,
            }
        )
        return f"{asset_type}-result"

    def get_content(self, asset_id):
        return f"/tmp/{asset_id}", "application/octet-stream"

    def get(self, asset_id):
        return {"id": asset_id, "type": "image"}


class _RecoveryGateway:
    async def generate_image(
        self,
        route,
        prompt,
        parameters,
        input_asset_paths,
        input_asset_paths_by_parameter=None,
    ):
        return {"data": [{"url": "http://example.test/image.png"}]}

    async def get_video_status(self, route, provider_task_id):
        return {
            "status": "succeeded",
            "progress": 100,
            "video_url": "http://example.test/video.mp4",
        }


def test_task_view_exposes_persisted_production_origin(tmp_path) -> None:
    database = Database(tmp_path / "task-origin.db")
    repository = GenerationTaskRepository(database)
    origin = {
        "kind": "drama_production_run",
        "projectId": "project-1",
        "episodeId": "episode-1",
        "productionRunId": "run-1",
        "stage": "assets",
        "targetType": "entity",
        "targetId": "entity-1",
        "slot": "primary",
    }
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 prompt, original_request_json, normalized_request_json,
                 status, result_asset_ids_json)
            VALUES (?, ?, 'local-user', 'comfyui', 'comfy-flux-image',
                    'image_generation', 'origin test', ?, '{}',
                    'succeeded', '[]')
            """,
            (
                "task-origin",
                "request-origin",
                json.dumps({"origin": origin}, ensure_ascii=False),
            ),
        )
    service = GenerationService(
        repository,
        _RecoveryProviders(),
        _RecoveryAssets(),
        _RecoveryGateway(),
    )

    task = service.get("task-origin")

    assert task["origin"] == origin
    database.close()


def test_failed_task_can_retry_from_persisted_request(tmp_path) -> None:
    database = Database(tmp_path / "retry.db")
    repository = GenerationTaskRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 prompt, original_request_json, normalized_request_json,
                 status, completed_at)
            VALUES ('task-failed', 'request-failed', 'local-user',
                    'comfyui', 'comfy-flux-image', 'image_generation',
                    'retry me',
                    '{}',
                    '{"providerId":"comfyui","modelId":"comfy-flux-image",
                    "taskType":"image_generation","prompt":"retry me",
                    "inputAssetIds":[],"references":{"image":[]},
                    "parameters":{}}',
                    'failed', CURRENT_TIMESTAMP)
            """
        )
    service = GenerationService(
        repository,
        _RecoveryProviders(),
        _RecoveryAssets(),
        _RecoveryGateway(),
    )

    retried = asyncio.run(service.retry("task-failed"))

    assert retried["id"] != "task-failed"
    assert retried["prompt"] == "retry me"
    assert retried["taskType"] == "image_generation"
    database.close()


def test_video_task_resumes_provider_polling_after_restart(tmp_path) -> None:
    database = Database(tmp_path / "resume.db")
    repository = GenerationTaskRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO generation_tasks
                (id, request_id, user_id, provider_id, model_id, task_type,
                 prompt, original_request_json, normalized_request_json,
                 status, provider_task_id)
            VALUES ('task-resume', 'request-resume', 'local-user',
                    'comfyui', 'comfy-wan-video', 'video_generation',
                    'resume me', '{}', '{}', 'running', 'prompt-existing')
            """
        )
    assets = _RecoveryAssets()
    service = GenerationService(
        repository,
        _RecoveryProviders(),
        assets,
        _RecoveryGateway(),
    )

    async def resume():
        count = await service.resume_interrupted()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return count, repository.get("task-resume")

    resumed, task = asyncio.run(resume())
    assert resumed == 1
    assert task is not None
    assert task["status"] == "succeeded"
    assert task["result_asset_ids"] == ["video-result"]
    assert assets.imported[0]["assetType"] == "video"
    database.close()
