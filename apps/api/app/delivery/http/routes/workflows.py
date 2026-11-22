"""HTTP routes for ComfyUI workflow model management."""

from fastapi import APIRouter

from app.delivery.http.schemas.workflows import (
    WorkflowImportRequest,
    WorkflowParametersUpdate,
    WorkflowTestRequest,
)
from app.modules.workflows import WorkflowService


def create_workflow_router(service: WorkflowService) -> APIRouter:
    router = APIRouter(prefix="/api/comfy", tags=["comfy-workflows"])

    @router.get("/workflows")
    async def list_workflows():
        return await service.discover()

    @router.post("/workflows/import")
    async def import_workflow(payload: WorkflowImportRequest):
        return await service.import_workflow(
            filename=payload.filename,
            name=payload.name,
            capability=payload.capability,
        )

    @router.post("/workflows/{workflow_id}/test")
    async def test_workflow(workflow_id: str, payload: WorkflowTestRequest):
        return await service.test_workflow(
            workflow_id, payload.prompt, payload.asset_ids
        )

    @router.get("/workflows/{workflow_id}/inputs")
    async def workflow_inputs(workflow_id: str):
        return await service.inputs(workflow_id)

    @router.patch("/workflows/{workflow_id}")
    async def toggle_workflow(workflow_id: str, enabled: bool):
        return service.set_enabled(workflow_id, enabled)

    @router.put("/workflows/{workflow_id}/parameters")
    async def update_parameters(
        workflow_id: str, payload: WorkflowParametersUpdate
    ):
        return service.update_parameters(workflow_id, payload.parameters)

    @router.delete("/workflows/{workflow_id}")
    async def delete_workflow(workflow_id: str):
        return service.delete(workflow_id)

    return router
