"""HTTP routes for durable creative projects and novel workflows."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.delivery.http.schemas.creative_projects import (
    NovelProjectCreate,
    ScreenplayProjectCreate,
)
from app.modules.creative_projects import CreativeProjectService


def create_creative_project_router(
    service: CreativeProjectService,
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
            return service.inspect_quality(project_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/{project_id}/impact/{step_key}")
    async def inspect_impact(project_id: str, step_key: str):
        try:
            return service.inspect_impact(project_id, step_key)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/{project_id}/artifacts/{step_key}/approve")
    async def approve_artifact(project_id: str, step_key: str):
        try:
            return service.approve_artifact(project_id, step_key)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/{project_id}/retry")
    async def retry_project(project_id: str):
        try:
            return service.retry_project(project_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    return router
