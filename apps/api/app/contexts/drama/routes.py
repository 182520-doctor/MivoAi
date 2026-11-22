"""HTTP routes for short-drama project lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.contexts.drama.application import DramaProjectService
from app.contexts.drama.domain import DramaEpisodePlan, DramaSceneContract
from app.contexts.drama.schemas import (
    DramaAssetBinding,
    DramaAssetCandidateUpdate,
    DramaAudioMixUpdate,
    DramaDocumentCreate,
    DramaDocumentUpdate,
    DramaEntityCreate,
    DramaEntityPromptUpdate,
    DramaEntityUpdate,
    DramaEpisodeCreate,
    DramaEpisodePlanUpdate,
    DramaEpisodeRenderRequest,
    DramaProductionRunCreate,
    DramaProductionRunStart,
    DramaProjectCreate,
    DramaProjectUpdate,
    DramaReviewCreate,
    DramaSceneCreate,
    DramaShotCreate,
    DramaShotDirectionInput,
    DramaShotPromptUpdate,
    DramaShotReferencesUpdate,
    DramaShotUpdate,
    DramaStageDecision,
    DramaSubtitleStyleUpdate,
    DramaSubtitlesUpdate,
)


def create_drama_router(service: DramaProjectService) -> APIRouter:
    router = APIRouter(prefix="/api/drama/projects", tags=["drama"])

    @router.get("")
    async def list_projects(limit: int = 100):
        return service.list_projects(limit)

    @router.get("/roles")
    async def list_roles(stage: str | None = None):
        return service.roles(stage=stage)

    @router.post("")
    async def create_project(payload: DramaProjectCreate):
        return service.create_project(
            idea=payload.idea,
            title=payload.title,
            project_format=payload.project_format,
            visual_style=payload.visual_style,
        )

    @router.get("/{project_id}")
    async def get_project(project_id: str):
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="短剧项目不存在")
        return project

    @router.patch("/{project_id}")
    async def update_project(project_id: str, payload: DramaProjectUpdate):
        project = service.update_stage(
            project_id,
            active_stage=payload.active_stage,
            status=payload.status,
        )
        if not project:
            raise HTTPException(status_code=404, detail="短剧项目不存在")
        return project

    @router.get("/{project_id}/documents")
    async def list_documents(project_id: str):
        return service.list_documents(project_id)

    @router.post("/{project_id}/documents")
    async def create_document(project_id: str, payload: DramaDocumentCreate):
        return service.create_document(
            project_id,
            kind=payload.kind,
            title=payload.title,
            content=payload.content,
        )

    @router.patch("/documents/{document_id}")
    async def update_document(
        document_id: str,
        payload: DramaDocumentUpdate,
    ):
        document = service.update_document(
            document_id,
            title=payload.title,
            content=payload.content,
        )
        if not document:
            raise HTTPException(status_code=404, detail="短剧文档不存在")
        return document

    @router.post("/documents/{document_id}/approve")
    async def approve_document(document_id: str):
        document = service.approve_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="短剧文档不存在")
        return document

    @router.get("/{project_id}/production")
    async def production(project_id: str):
        return service.production(project_id)

    @router.get("/{project_id}/production-runs")
    async def list_production_runs(
        project_id: str,
        episode_id: str | None = Query(default=None, alias="episodeId"),
        limit: int = 50,
    ):
        return service.list_production_runs(
            project_id,
            episode_id=episode_id,
            limit=limit,
        )

    @router.post("/{project_id}/episodes/{episode_id}/production-runs")
    async def create_production_run(
        project_id: str,
        episode_id: str,
        payload: DramaProductionRunCreate,
    ):
        return service.create_production_run(
            project_id,
            episode_id=episode_id,
            stage=payload.stage,
            name=payload.name,
            requires_approval=payload.requires_approval,
            max_parallel=payload.max_parallel,
            items=[
                item.model_dump(by_alias=True)
                for item in payload.items
            ],
        )

    @router.get("/production-runs/{run_id}")
    async def get_production_run(run_id: str):
        return service.get_production_run(run_id)

    @router.post("/production-runs/{run_id}/start")
    async def start_production_run(
        run_id: str,
        payload: DramaProductionRunStart | None = None,
    ):
        options = payload or DramaProductionRunStart()
        return service.start_production_run(
            run_id,
            approved_by=options.approved_by,
        )

    @router.post("/production-runs/{run_id}/cancel")
    async def cancel_production_run(run_id: str):
        return service.cancel_production_run(run_id)

    @router.post("/production-runs/{run_id}/retry-failed")
    async def retry_failed_production_run(
        run_id: str,
        payload: DramaProductionRunStart | None = None,
    ):
        options = payload or DramaProductionRunStart()
        return service.retry_failed_production_run(
            run_id,
            approved_by=options.approved_by,
        )

    @router.get("/{project_id}/asset-candidates")
    async def list_asset_candidates(
        project_id: str,
        subject_type: str | None = Query(default=None, alias="subjectType"),
        subject_id: str | None = Query(default=None, alias="subjectId"),
        slot: str | None = None,
    ):
        return service.list_asset_candidates(
            project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            slot=slot,
        )

    @router.patch("/asset-candidates/{candidate_id}")
    async def update_asset_candidate(
        candidate_id: str,
        payload: DramaAssetCandidateUpdate,
    ):
        return service.update_asset_candidate_status(
            candidate_id,
            status=payload.status,
        )

    @router.get("/{project_id}/audit")
    async def audit(project_id: str):
        return service.audit(project_id)

    @router.get("/{project_id}/script-audit")
    async def audit_script(project_id: str):
        return service.audit_script(project_id)

    @router.get("/{project_id}/production-control")
    async def production_control(project_id: str):
        return service.production_control(project_id)

    @router.get("/{project_id}/series-production")
    async def series_production(project_id: str):
        return service.series_production(project_id)

    @router.get("/{project_id}/reviews")
    async def list_reviews(project_id: str, stage: str | None = None):
        return service.list_reviews(project_id, stage=stage)

    @router.post("/{project_id}/reviews")
    async def create_review(project_id: str, payload: DramaReviewCreate):
        return service.record_review(
            project_id,
            stage=payload.stage,
            role_id=payload.role_id,
            status=payload.status,
            score=payload.score,
            checklist=[
                {
                    "key": item.key,
                    "label": item.label,
                    "passed": item.passed,
                    "note": item.note,
                }
                for item in payload.checklist
            ],
            feedback=payload.feedback,
            reviewer=payload.reviewer,
        )

    @router.post("/{project_id}/stages/{stage}/approve")
    async def approve_stage(
        project_id: str,
        stage: str,
        payload: DramaStageDecision | None = None,
    ):
        options = payload or DramaStageDecision()
        return service.decide_stage(
            project_id,
            stage=stage,
            approved=True,
            feedback=options.feedback,
        )

    @router.post("/{project_id}/stages/{stage}/request-changes")
    async def request_stage_changes(
        project_id: str,
        stage: str,
        payload: DramaStageDecision | None = None,
    ):
        options = payload or DramaStageDecision()
        return service.decide_stage(
            project_id,
            stage=stage,
            approved=False,
            feedback=options.feedback,
        )

    @router.post("/{project_id}/episodes")
    async def create_episode(
        project_id: str,
        payload: DramaEpisodeCreate,
    ):
        return service.create_episode(
            project_id,
            title=payload.title,
            synopsis=payload.synopsis,
        )

    @router.put("/episodes/{episode_id}/plan")
    async def update_episode_plan(
        episode_id: str,
        payload: DramaEpisodePlanUpdate,
    ):
        return service.update_episode_plan(
            episode_id,
            plan=service_episode_plan(payload),
        )

    @router.get("/episodes/{episode_id}/production")
    async def episode_production(episode_id: str):
        return service.episode_production(episode_id)

    @router.get("/episodes/{episode_id}/audit")
    async def audit_episode(episode_id: str):
        return service.audit_episode(episode_id)

    @router.get("/episodes/{episode_id}/export-manifests")
    async def list_export_manifests(episode_id: str):
        return service.export_manifests(episode_id)

    @router.post("/episodes/{episode_id}/scenes")
    async def create_scene(episode_id: str, payload: DramaSceneCreate):
        return service.create_scene(
            episode_id,
            heading=payload.heading,
            summary=payload.summary,
            script_document_id=payload.script_document_id,
        )

    @router.post("/episodes/{episode_id}/render")
    async def render_episode(
        episode_id: str,
        payload: DramaEpisodeRenderRequest | None = None,
    ):
        options = payload or DramaEpisodeRenderRequest()
        return await service.render_episode(
            episode_id,
            transition=options.transition,
            transition_duration=options.transition_duration,
            strict_approvals=options.strict_approvals,
        )

    @router.get("/episodes/{episode_id}/subtitles")
    async def get_subtitles(episode_id: str):
        return {"cues": service.subtitles(episode_id)}

    @router.put("/episodes/{episode_id}/subtitles")
    async def update_subtitles(
        episode_id: str,
        payload: DramaSubtitlesUpdate,
    ):
        return {
            "cues": service.update_subtitles(
                episode_id,
                [
                    {
                        "startSeconds": cue.start_seconds,
                        "endSeconds": cue.end_seconds,
                        "text": cue.text,
                    }
                    for cue in payload.cues
                ],
            )
        }

    @router.put("/episodes/{episode_id}/audio-mix")
    async def update_audio_mix(
        episode_id: str,
        payload: DramaAudioMixUpdate,
    ):
        return service.update_audio_mix(
            episode_id,
            music_asset_id=payload.music_asset_id,
            music_volume_db=payload.music_volume_db,
            ambience_asset_id=payload.ambience_asset_id,
            ambience_volume_db=payload.ambience_volume_db,
            ducking=payload.ducking,
            sound_effects=[
                {
                    "assetId": effect.asset_id,
                    "startSeconds": effect.start_seconds,
                    "durationSeconds": effect.duration_seconds,
                    "volumeDb": effect.volume_db,
                }
                for effect in payload.sound_effects
            ],
        )

    @router.put("/episodes/{episode_id}/subtitle-style")
    async def update_subtitle_style(
        episode_id: str,
        payload: DramaSubtitleStyleUpdate,
    ):
        return service.update_subtitle_style(
            episode_id,
            preset=payload.preset,
            font_size=payload.font_size,
            outline=payload.outline,
            margin_v=payload.margin_v,
            primary_color=payload.primary_color,
            outline_color=payload.outline_color,
        )

    @router.post("/scenes/{scene_id}/shots")
    async def create_shot(scene_id: str, payload: DramaShotCreate):
        return service.create_shot(
            scene_id,
            title=payload.title,
            description=payload.description,
            dialogue=payload.dialogue,
            duration_seconds=payload.duration_seconds,
            direction=payload.direction.model_dump(by_alias=True),
        )

    @router.patch("/shots/{shot_id}")
    async def update_shot(shot_id: str, payload: DramaShotUpdate):
        has_asset_update = any(
            value is not None
            for value in (
                payload.first_frame_asset_id,
                payload.last_frame_asset_id,
                payload.grid9_asset_id,
                payload.storyboard_asset_id,
                payload.video_asset_id,
                payload.audio_asset_id,
            )
        )
        shot = service.update_shot(
            shot_id,
            status=payload.status,
            first_frame_asset_id=payload.first_frame_asset_id,
            last_frame_asset_id=payload.last_frame_asset_id,
            grid9_asset_id=payload.grid9_asset_id,
            storyboard_asset_id=payload.storyboard_asset_id,
            video_asset_id=payload.video_asset_id,
            audio_asset_id=payload.audio_asset_id,
            direction=(
                payload.direction.model_dump(by_alias=True)
                if payload.direction is not None
                else None
            ),
            status_reviewer="system" if has_asset_update else "user",
            status_note=(
                payload.review_note
                or (
                    "镜头素材更新，自动重置审核状态"
                    if has_asset_update
                    else ""
                )
            ),
        )
        if not shot:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return shot

    @router.get("/shots/{shot_id}/status-history")
    async def get_shot_status_history(shot_id: str, limit: int = 50):
        history = service.shot_status_history(shot_id, limit=limit)
        if history is None:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return {"events": history}

    @router.put("/shots/{shot_id}/prompts/{slot}")
    async def update_shot_prompt(
        shot_id: str,
        slot: str,
        payload: DramaShotPromptUpdate,
    ):
        shot = service.update_shot_prompt(
            shot_id,
            slot=slot,
            prompt=payload.prompt,
        )
        if not shot:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return shot

    @router.put("/shots/{shot_id}/direction")
    async def update_shot_direction(
        shot_id: str,
        payload: DramaShotDirectionInput,
    ):
        shot = service.update_shot_direction(
            shot_id,
            direction=payload.model_dump(by_alias=True),
        )
        if not shot:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return shot

    @router.get("/{project_id}/entities")
    async def list_entities(project_id: str):
        return service.list_entities(project_id)

    @router.post("/{project_id}/entities")
    async def create_entity(
        project_id: str,
        payload: DramaEntityCreate,
    ):
        return service.create_entity(
            project_id,
            kind=payload.kind,
            name=payload.name,
            description=payload.description,
            profile=payload.profile,
        )

    @router.patch("/entities/{entity_id}")
    async def update_entity(
        entity_id: str,
        payload: DramaEntityUpdate,
    ):
        entity = service.update_entity(
            entity_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            primary_asset_id=payload.primary_asset_id,
            reference_asset_ids=payload.reference_asset_ids,
            asset_slots=payload.asset_slots,
            profile=payload.profile,
            voice_name=payload.voice_name,
            voice_rate=payload.voice_rate,
        )
        if not entity:
            raise HTTPException(status_code=404, detail="短剧实体不存在")
        return entity

    @router.put("/entities/{entity_id}/asset-slots/{slot}")
    async def bind_entity_asset(
        entity_id: str,
        slot: str,
        payload: DramaAssetBinding,
    ):
        return service.bind_entity_asset(
            entity_id,
            slot=slot,
            asset_id=payload.asset_id,
        )

    @router.put("/entities/{entity_id}/prompts/{slot}")
    async def update_entity_prompt(
        entity_id: str,
        slot: str,
        payload: DramaEntityPromptUpdate,
    ):
        entity = service.update_entity_prompt(
            entity_id,
            slot=slot,
            prompt=payload.prompt,
        )
        if not entity:
            raise HTTPException(status_code=404, detail="短剧实体不存在")
        return entity

    @router.get("/shots/{shot_id}/references")
    async def list_shot_references(shot_id: str):
        references = service.get_shot_references(shot_id)
        if references is None:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return {"references": references}

    @router.put("/shots/{shot_id}/references")
    async def update_shot_references(
        shot_id: str,
        payload: DramaShotReferencesUpdate,
    ):
        references = service.set_shot_references(
            shot_id,
            [
                {
                    "entityId": item.entity_id,
                    "role": item.role,
                }
                for item in payload.references
            ],
        )
        if references is None:
            raise HTTPException(status_code=404, detail="短剧镜头不存在")
        return {"references": references}

    @router.put("/shots/{shot_id}/asset-slots/{slot}")
    async def bind_shot_asset(
        shot_id: str,
        slot: str,
        payload: DramaAssetBinding,
    ):
        return service.bind_shot_asset(
            shot_id,
            slot=slot,
            asset_id=payload.asset_id,
        )

    return router


def service_episode_plan(payload: DramaEpisodePlanUpdate):
    return DramaEpisodePlan(
        time_scope=payload.time_scope,
        locations=tuple(payload.locations),
        interior_exterior=tuple(payload.interior_exterior),
        characters=tuple(payload.characters),
        scenes=tuple(payload.scenes),
        story_beats=tuple(payload.story_beats),
        visual_requirements=tuple(payload.visual_requirements),
        dialogue_requirements=tuple(payload.dialogue_requirements),
        continuity_risks=tuple(payload.continuity_risks),
        scene_contracts=tuple(
            DramaSceneContract(
                scene_number=item.scene_number,
                title=item.title,
                value_in=item.value_in,
                character_objectives=tuple(item.character_objectives),
                obstacle=item.obstacle,
                tactics=tuple(item.tactics),
                beats=tuple(item.beats),
                turn=item.turn,
                value_out=item.value_out,
                subtext=item.subtext,
                visual_strategy=item.visual_strategy,
                performance_notes=item.performance_notes,
                sound_notes=item.sound_notes,
            )
            for item in payload.scene_contracts
        ),
    )
