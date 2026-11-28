"""ComfyUI workflow discovery, import, test, and model registration."""

from __future__ import annotations

import os
from pathlib import Path

from app.modules.workflows.converter import (
    apply_bindings,
    apply_parameter_schema,
    build_input_catalog,
    build_topology_from_graph,
    convert_ui_workflow,
    validate_parameter_schema,
)
from app.modules.workflows.domain import ComfyWorkflowRecord
from app.modules.workflows.ports import (
    ComfyCatalogPort,
    WorkflowAssetRecorder,
    WorkflowRepositoryPort,
)
from app.shared.config import DEFAULT_COMFYUI_URL
from app.shared.errors import AppServerError, ProviderConfigurationError
from app.shared.semantic_parameters import infer_semantic_key


class WorkflowService:
    """Turn user ComfyUI workflows into configurable platform models."""

    def __init__(
        self,
        repository: WorkflowRepositoryPort,
        comfyui: ComfyCatalogPort,
        assets: WorkflowAssetRecorder,
        *,
        comfyui_url: str | None = None,
    ) -> None:
        self._repository = repository
        self._comfyui = comfyui
        self._assets = assets
        self._base_url = (
            comfyui_url
            or os.getenv("ZAOJING_COMFYUI_URL", DEFAULT_COMFYUI_URL)
        ).strip().rstrip("/") or DEFAULT_COMFYUI_URL

    async def discover(self) -> dict[str, object]:
        try:
            filenames = await self._comfyui.list_workflows(self._base_url)
        except AppServerError as exc:
            return {
                "comfyuiUrl": self._base_url,
                "available": False,
                "error": str(exc),
                "workflows": [],
            }
        imported = {record.source_filename: record for record in self._repository.list()}
        workflows = []
        for filename in filenames:
            record = imported.get(filename)
            workflows.append(
                {
                    "filename": filename,
                    "imported": bool(record),
                    "workflowId": record.id if record else None,
                    "name": record.name if record else Path(filename).stem,
                    "capability": record.capability if record else None,
                    "status": record.status if record else "available",
                    "modelId": record.model_id if record else None,
                    "testAssetId": record.test_asset_id if record else None,
                    "testMessage": record.test_message if record else None,
                    "parameters": record.parameter_schema if record else [],
                }
            )
        return {
            "comfyuiUrl": self._base_url,
            "available": True,
            "error": None,
            "workflows": workflows,
        }

    async def import_workflow(
        self,
        *,
        filename: str,
        name: str | None,
        capability: str,
    ) -> dict[str, object]:
        ui_workflow = await self._comfyui.load_ui_workflow(
            self._base_url, filename
        )
        object_info = await self._comfyui.get_object_info(self._base_url)
        converted = convert_ui_workflow(
            ui_workflow,
            capability=capability,
            object_info=object_info,
        )
        record = self._repository.upsert(
            source_filename=filename,
            name=name or Path(filename).stem,
            converted=converted,
        )
        return self._view(record)

    async def test_workflow(
        self,
        workflow_id: str,
        prompt: str,
        asset_ids: list[str] | None = None,
    ) -> dict[str, object]:
        record = self._require(workflow_id)
        uploaded_by_type: dict[str, list[str]] = {}
        for asset_id in asset_ids or []:
            asset = self._assets.get(asset_id)
            uploaded_name = await self._comfyui.upload_image(
                self._base_url,
                self._assets.get_content(asset_id)[0],
            )
            asset_type = str(asset.get("type") or "file")
            uploaded_by_type.setdefault(asset_type, []).append(uploaded_name)
        if record.parameter_schema:
            test_values = _workflow_test_values(record, prompt)
            asset_parameters = [
                parameter
                for parameter in record.parameter_schema
                if parameter.get("type") == "assets"
            ]
            remaining_by_type = {
                key: list(values) for key, values in uploaded_by_type.items()
            }
            uploaded_by_parameter: dict[str, list[str]] = {}
            for index, parameter in enumerate(asset_parameters):
                key = str(parameter.get("key") or f"assets_{index}")
                asset_type = str(parameter.get("assetType") or "image")
                remaining = remaining_by_type.setdefault(asset_type, [])
                capacity = len(parameter.get("bindings") or [])
                maximum = parameter.get("max")
                if isinstance(maximum, int) and maximum >= 0:
                    capacity = min(capacity, maximum)
                selected = remaining[:capacity]
                remaining_by_type[asset_type] = remaining[capacity:]
                uploaded_by_parameter[key] = selected
            compiled = apply_parameter_schema(
                record.api_graph,
                record.parameter_schema,
                values=test_values,
                uploaded_assets=[
                    item
                    for values in uploaded_by_type.values()
                    for item in values
                ],
                uploaded_assets_by_parameter=uploaded_by_parameter,
            )
        else:
            compiled = apply_bindings(
                record.api_graph,
                record.bindings,
                prompt=prompt,
                parameters={},
            )
        try:
            artifacts = await self._comfyui.execute_graph(
                self._base_url,
                compiled,
                timeout=(
                    1800
                    if record.capability
                    in {"video_generation", "video_processing"}
                    else 600
                ),
            )
        except Exception as exc:
            self._repository.save_test_result(
                workflow_id,
                asset_id=None,
                message=str(exc),
                success=False,
            )
            raise
        imported_ids: list[str] = []
        asset_type = {
            "image_processing": "image",
            "video_generation": "video",
            "video_processing": "video",
            "audio_processing": "audio",
            "transcription": "file",
        }.get(record.capability, "image")
        for artifact in artifacts:
            imported_ids.append(
                await self._assets.import_remote(
                    url=str(artifact["url"]),
                    session_id=None,
                    task_id=None,
                    asset_type=asset_type,
                    filename=str(artifact["filename"]),
                    metadata={
                        "workflowId": record.id,
                        "sourceFilename": record.source_filename,
                        "originalFilename": str(artifact["filename"]),
                        "test": True,
                    },
                )
            )
        asset_id = imported_ids[0]
        self._repository.save_test_result(
            workflow_id,
            asset_id=asset_id,
            message="工作流测试通过",
            success=True,
        )
        result = self._view(self._require(workflow_id))
        result["testAssetUrl"] = f"/api/assets/{asset_id}"
        result["testAssetUrls"] = [
            f"/api/assets/{item}" for item in imported_ids
        ]
        return result

    def set_enabled(self, workflow_id: str, enabled: bool) -> dict[str, object]:
        self._repository.set_enabled(workflow_id, enabled)
        return self._view(self._require(workflow_id))

    def update_parameters(
        self, workflow_id: str, parameters: list[dict[str, object]]
    ) -> dict[str, object]:
        record = self._require(workflow_id)
        validate_parameter_schema(record.api_graph, parameters)
        self._repository.update_parameters(workflow_id, parameters)
        return self._view(self._require(workflow_id))

    def delete(self, workflow_id: str) -> dict[str, object]:
        if not self._repository.delete(workflow_id):
            raise ProviderConfigurationError("工作流不存在")
        return {"workflowId": workflow_id, "deleted": True}

    async def inputs(self, workflow_id: str) -> dict[str, object]:
        record = self._require(workflow_id)
        topology = record.topology
        if (
            not record.input_catalog
            or not topology.get("nodes")
            or topology.get("source") != "ui_workflow"
        ):
            object_info = await self._comfyui.get_object_info(self._base_url)
            catalog = build_input_catalog(record.api_graph, object_info)
            topology = build_topology_from_graph(record.api_graph)
            try:
                ui_workflow = await self._comfyui.load_ui_workflow(
                    self._base_url,
                    record.source_filename,
                )
                converted = convert_ui_workflow(
                    ui_workflow,
                    capability=record.capability,
                    object_info=object_info,
                )
                if _compatible_graphs(converted.api_graph, record.api_graph):
                    catalog = list(converted.input_catalog)
                    topology = converted.topology
            except Exception:
                # A changed or unavailable source keeps the safe API-graph fallback.
                pass
            self._repository.update_input_catalog(
                workflow_id,
                catalog,
                topology,
            )
            record = self._require(workflow_id)
        return {
            "workflowId": record.id,
            "inputs": record.input_catalog,
            "parameters": record.parameter_schema,
            "topology": record.topology,
        }

    def _require(self, workflow_id: str) -> ComfyWorkflowRecord:
        record = self._repository.get(workflow_id)
        if not record:
            raise ProviderConfigurationError("工作流不存在")
        return record

    @staticmethod
    def _view(record: ComfyWorkflowRecord) -> dict[str, object]:
        return {
            "id": record.id,
            "sourceFilename": record.source_filename,
            "name": record.name,
            "capability": record.capability,
            "status": record.status,
            "bindings": record.bindings,
            "parameters": record.parameter_schema,
            "inputs": record.input_catalog,
            "outputNodeId": record.output_node_id,
            "modelId": record.model_id,
            "testAssetId": record.test_asset_id,
            "testMessage": record.test_message,
        }


def _compatible_graphs(
    current: dict[str, object],
    stored: dict[str, object],
) -> bool:
    if not isinstance(current, dict) or not isinstance(stored, dict):
        return False
    if set(current) != set(stored):
        return False
    for node_id, stored_node in stored.items():
        current_node = current.get(node_id)
        if not isinstance(current_node, dict) or not isinstance(stored_node, dict):
            return False
        if current_node.get("class_type") != stored_node.get("class_type"):
            return False
        current_inputs = current_node.get("inputs")
        stored_inputs = stored_node.get("inputs")
        if not isinstance(current_inputs, dict) or not isinstance(
            stored_inputs, dict
        ):
            return False
        if set(current_inputs) != set(stored_inputs):
            return False
    return True


def _workflow_test_values(
    record: ComfyWorkflowRecord,
    prompt: str,
) -> dict[str, object]:
    """Use saved workflow defaults so testing does not fail on derived controls."""

    values: dict[str, object] = {"prompt": prompt}
    for parameter in record.parameter_schema:
        default = parameter.get("default")
        if default in (None, ""):
            continue
        key = str(parameter.get("key") or "")
        semantic_key = str(
            parameter.get("semanticKey")
            or infer_semantic_key(
                key,
                str(parameter.get("label") or ""),
            )
        )
        values[key] = default
        values[semantic_key] = default
    for item in record.input_catalog:
        default = item.get("default")
        if default in (None, ""):
            continue
        key = str(item.get("field") or "")
        semantic_key = str(
            item.get("semanticKey")
            or infer_semantic_key(
                key,
                str(item.get("fieldLabel") or item.get("label") or ""),
                key,
            )
        )
        values[key] = default
        values[semantic_key] = default
    return values
