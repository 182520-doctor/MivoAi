"""HTTP endpoints for durable creative projects and novel workflows."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.creative_project_service import CreativeProjectService
from app.services.quality_gate_service import QualityGateService


class ScreenplayProjectCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    idea: str = Field(min_length=1, max_length=4000)
    targetMinutes: int = Field(default=3, ge=1, le=120)
    episodeCount: int = Field(default=1, ge=1, le=200)
    sessionId: str | None = None


class NovelProjectCreate(BaseModel):
    title: str = Field(default="", max_length=80)
    idea: str = Field(min_length=1, max_length=4000)
    targetWords: int = Field(default=3000, ge=500, le=300000)
    chapterCount: int = Field(default=1, ge=1, le=200)
    sessionId: str | None = None


def create_creative_project_router(
    service: CreativeProjectService, quality_gate: QualityGateService | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/creative-projects", tags=["creative-projects"])

    @router.get("")
    async def list_projects():
        return service.list_projects()

    @router.get("/file")
    async def get_project_file(path: str):
        try:
            artifact = service.resolve_public_file(path)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(403, str(exc)) from exc
        media_type = (
            "text/markdown; charset=utf-8"
            if artifact.suffix.lower() == ".md"
            else "text/plain; charset=utf-8"
        )
        return FileResponse(artifact, media_type=media_type)

    @router.post("/screenplay")
    async def create_screenplay_project(payload: ScreenplayProjectCreate):
        return service.create_screenplay_project(
            title=payload.title,
            idea=payload.idea,
            target_minutes=payload.targetMinutes,
            episode_count=payload.episodeCount,
            session_id=payload.sessionId,
        )

    @router.post("/novel")
    async def create_novel_project(payload: NovelProjectCreate):
        return service.create_novel_project(
            title=payload.title,
            idea=payload.idea,
            target_words=payload.targetWords,
            chapter_count=payload.chapterCount,
            session_id=payload.sessionId,
        )

    @router.get("/{project_id}")
    async def get_project(project_id: str):
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(404, "创作项目不存在")
        return project

    @router.get("/{project_id}/files/{artifact_path:path}")
    async def get_project_artifact(project_id: str, artifact_path: str):
        try:
            artifact = service.resolve_project_file(project_id, artifact_path)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            status = 404 if "项目不存在" in str(exc) else 403
            raise HTTPException(status, str(exc)) from exc
        media_type = (
            "text/markdown; charset=utf-8"
            if artifact.suffix.lower() == ".md"
            else "text/plain; charset=utf-8"
        )
        return FileResponse(artifact, media_type=media_type)

    @router.get("/{project_id}/director-prompt")
    async def get_director_prompt(project_id: str):
        try:
            return {"prompt": service.build_director_prompt(project_id)}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/{project_id}/novel-prompt")
    async def get_novel_prompt(project_id: str):
        try:
            return {"prompt": service.build_novel_prompt(project_id)}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/{project_id}/quality")
    async def inspect_quality(project_id: str):
        try:
            workspace = service.workspace_path(project_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return (quality_gate or QualityGateService()).inspect(workspace)

    @router.get("/{project_id}/impact/{step_key}")
    async def inspect_impact(project_id: str, step_key: str):
        if not service.get_project(project_id):
            raise HTTPException(404, "创作项目不存在")
        return QualityGateService.impact_analysis(step_key)

    @router.post("/{project_id}/artifacts/{step_key}/approve")
    async def approve_artifact(project_id: str, step_key: str):
        if not service.get_project(project_id):
            raise HTTPException(404, "创作项目不存在")
        workflow = service.get_project(project_id)["workflow"]
        step = next((item for item in workflow["steps"] if item["stepKey"] == step_key), None)
        if not step:
            raise HTTPException(404, "工作流阶段不存在")
        if not service.repository.update_step_status(project_id, step_key, "approved"):
            raise HTTPException(404, "阶段记录不存在")
        if step.get("artifactPath"):
            service.repository.update_artifact_status(
                project_id, str(step["artifactPath"]), "approved"
            )
        return service.get_project(project_id)

    @router.post("/{project_id}/retry")
    async def retry_project(project_id: str):
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(404, "创作项目不存在")
        service.repository.set_workflow_status(project_id, "ready")
        return {"projectId": project_id, "status": "ready", "message": "项目已准备重新执行"}

    return router
