"""Ports used by workflow imports for ComfyUI access and asset recording."""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.workflows.domain import ComfyWorkflowRecord, ConvertedWorkflow


class ComfyCatalogPort(Protocol):
    async def list_workflows(self, base_url: str) -> list[str]: ...

    async def load_ui_workflow(
        self, base_url: str, filename: str
    ) -> dict[str, Any]: ...

    async def get_object_info(self, base_url: str) -> dict[str, Any]: ...

    async def upload_image(self, base_url: str, path: str) -> str: ...

    async def execute_graph(
        self,
        base_url: str,
        graph: dict[str, Any],
        *,
        timeout: float = 600,
    ) -> list[dict[str, object]]: ...


class WorkflowAssetRecorder(Protocol):
    async def import_remote(
        self,
        *,
        url: str,
        session_id: str | None,
        task_id: str | None,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str: ...

    def get_content(self, asset_id: str) -> tuple[str, str | None]: ...


class WorkflowRepositoryPort(Protocol):
    def upsert(
        self,
        *,
        source_filename: str,
        name: str,
        converted: ConvertedWorkflow,
    ) -> ComfyWorkflowRecord: ...

    def get(self, workflow_id: str) -> ComfyWorkflowRecord | None: ...

    def list(self) -> list[ComfyWorkflowRecord]: ...

    def set_enabled(self, workflow_id: str, enabled: bool) -> None: ...

    def save_test_result(
        self,
        workflow_id: str,
        *,
        asset_id: str | None,
        message: str,
        success: bool,
    ) -> None: ...

    def update_parameters(
        self,
        workflow_id: str,
        parameters: list[dict[str, object]],
    ) -> None: ...

    def update_input_catalog(
        self,
        workflow_id: str,
        input_catalog: list[dict[str, object]],
        topology: dict[str, Any] | None = None,
    ) -> None: ...

    def delete(self, workflow_id: str) -> bool: ...
