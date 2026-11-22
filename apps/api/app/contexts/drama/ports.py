"""Persistence contract for short-drama projects."""

from __future__ import annotations

from typing import Protocol

from app.contexts.drama.domain import (
    DramaAudioMix,
    DramaDocument,
    DramaEntity,
    DramaEpisode,
    DramaEpisodePlan,
    DramaExportManifest,
    DramaProductionRun,
    DramaProductionRunItem,
    DramaProject,
    DramaReview,
    DramaReviewCheck,
    DramaScene,
    DramaShot,
    DramaShotEntityReference,
    DramaShotStatusEvent,
    DramaStageRevision,
    DramaSubtitleCue,
    DramaSubtitleStyle,
)


class DramaProjectRepositoryPort(Protocol):
    def list_projects(self, limit: int = 100) -> list[DramaProject]: ...

    def get_project(self, project_id: str) -> DramaProject | None: ...

    def create_project(
        self,
        *,
        project_id: str,
        title: str,
        idea: str,
        project_format: str,
        visual_style: str,
        workspace_path: str,
    ) -> DramaProject: ...

    def update_project_stage(
        self,
        project_id: str,
        *,
        active_stage: str,
        status: str | None = None,
    ) -> DramaProject | None: ...

    def list_documents(self, project_id: str) -> list[DramaDocument]: ...

    def get_document(self, document_id: str) -> DramaDocument | None: ...

    def create_document(
        self,
        *,
        document_id: str,
        project_id: str,
        kind: str,
        title: str,
        content: str,
    ) -> DramaDocument: ...

    def update_document(
        self,
        document_id: str,
        *,
        title: str,
        content: str,
    ) -> DramaDocument | None: ...

    def approve_document(self, document_id: str) -> DramaDocument | None: ...

    def list_episodes(self, project_id: str) -> list[DramaEpisode]: ...

    def get_episode(self, episode_id: str) -> DramaEpisode | None: ...

    def create_episode(
        self,
        *,
        episode_id: str,
        project_id: str,
        title: str,
        synopsis: str,
        plan: DramaEpisodePlan | None = None,
    ) -> DramaEpisode: ...

    def update_episode_plan(
        self,
        episode_id: str,
        *,
        plan: DramaEpisodePlan,
    ) -> DramaEpisode | None: ...

    def update_episode_export(
        self,
        episode_id: str,
        *,
        export_asset_id: str,
        export_manifest_id: str,
    ) -> DramaEpisode | None: ...

    def create_export_manifest(
        self,
        *,
        manifest_id: str,
        project_id: str,
        episode_id: str,
        export_asset_id: str,
        manifest: dict[str, object],
    ) -> DramaExportManifest: ...

    def list_export_manifests(
        self,
        episode_id: str,
    ) -> list[DramaExportManifest]: ...

    def update_episode_subtitles(
        self,
        episode_id: str,
        *,
        cues: list[DramaSubtitleCue],
    ) -> DramaEpisode | None: ...

    def update_episode_audio_mix(
        self,
        episode_id: str,
        *,
        audio_mix: DramaAudioMix,
    ) -> DramaEpisode | None: ...

    def update_episode_subtitle_style(
        self,
        episode_id: str,
        *,
        subtitle_style: DramaSubtitleStyle,
    ) -> DramaEpisode | None: ...

    def list_scenes(self, episode_id: str) -> list[DramaScene]: ...

    def get_scene(self, scene_id: str) -> DramaScene | None: ...

    def create_scene(
        self,
        *,
        scene_id: str,
        episode_id: str,
        heading: str,
        summary: str,
        script_document_id: str | None,
    ) -> DramaScene: ...

    def list_shots(self, scene_id: str) -> list[DramaShot]: ...

    def get_shot(self, shot_id: str) -> DramaShot | None: ...

    def create_shot(
        self,
        *,
        shot_id: str,
        scene_id: str,
        title: str,
        description: str,
        dialogue: str,
        duration_seconds: float,
        direction: dict[str, str] | None = None,
    ) -> DramaShot: ...

    def update_shot_status(
        self,
        shot_id: str,
        *,
        status: str,
    ) -> DramaShot | None: ...

    def update_shot(
        self,
        shot_id: str,
        *,
        status: str | None = None,
        first_frame_asset_id: str | None = None,
        last_frame_asset_id: str | None = None,
        grid9_asset_id: str | None = None,
        storyboard_asset_id: str | None = None,
        video_asset_id: str | None = None,
        audio_asset_id: str | None = None,
        direction: dict[str, str] | None = None,
    ) -> DramaShot | None: ...

    def update_shot_prompt(
        self,
        shot_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> DramaShot | None: ...

    def create_shot_status_event(
        self,
        *,
        event_id: str,
        shot_id: str,
        from_status: str,
        to_status: str,
        reviewer: str,
        note: str,
    ) -> DramaShotStatusEvent: ...

    def list_shot_status_events(
        self,
        shot_id: str,
        *,
        limit: int = 50,
    ) -> list[DramaShotStatusEvent]: ...

    def list_entities(self, project_id: str) -> list[DramaEntity]: ...

    def get_entity(self, entity_id: str) -> DramaEntity | None: ...

    def create_entity(
        self,
        *,
        entity_id: str,
        project_id: str,
        kind: str,
        name: str,
        description: str,
        profile: dict[str, str] | None = None,
    ) -> DramaEntity: ...

    def update_entity(
        self,
        entity_id: str,
        *,
        name: str,
        description: str,
        status: str,
        primary_asset_id: str | None,
        reference_asset_ids: list[str],
        asset_slots: dict[str, str] | None = None,
        profile: dict[str, str] | None = None,
        voice_name: str | None = None,
        voice_rate: float = 0,
    ) -> DramaEntity | None: ...

    def update_entity_prompt(
        self,
        entity_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> DramaEntity | None: ...

    def list_shot_references(
        self,
        shot_id: str,
    ) -> list[DramaShotEntityReference]: ...

    def replace_shot_references(
        self,
        shot_id: str,
        references: list[tuple[str, str]],
    ) -> list[DramaShotEntityReference]: ...

    def list_reviews(
        self,
        project_id: str,
        *,
        stage: str | None = None,
    ) -> list[DramaReview]: ...

    def create_review(
        self,
        *,
        review_id: str,
        project_id: str,
        stage: str,
        role_id: str,
        status: str,
        score: float,
        checklist: list[DramaReviewCheck],
        feedback: str,
        reviewer: str,
        artifact_revision: int,
    ) -> DramaReview: ...

    def get_stage_revision(
        self,
        project_id: str,
        stage: str,
    ) -> DramaStageRevision: ...

    def touch_stage_revisions(
        self,
        project_id: str,
        *,
        stages: list[str],
        reason: str,
    ) -> None: ...

    def set_stage_approval(
        self,
        project_id: str,
        *,
        stage: str,
        approved: bool,
        approved_by: str,
    ) -> DramaStageRevision: ...

    def list_production_runs(
        self,
        project_id: str,
        *,
        episode_id: str | None = None,
        limit: int = 50,
    ) -> list[DramaProductionRun]: ...

    def get_production_run(
        self,
        run_id: str,
    ) -> DramaProductionRun | None: ...

    def create_production_run(
        self,
        *,
        run_id: str,
        project_id: str,
        episode_id: str,
        stage: str,
        name: str,
        status: str,
        requires_approval: bool,
        max_parallel: int,
        items: list[dict[str, object]],
    ) -> DramaProductionRun: ...

    def update_production_run_status(
        self,
        run_id: str,
        *,
        status: str,
        approved_by: str | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> DramaProductionRun | None: ...

    def list_production_run_items(
        self,
        run_id: str,
    ) -> list[DramaProductionRunItem]: ...

    def update_production_run_item(
        self,
        item_id: str,
        *,
        status: str,
        generation_task_id: str | None = None,
        result_asset_id: str | None = None,
        error: str | None = None,
    ) -> DramaProductionRunItem | None: ...

    def reset_failed_production_run_items(
        self,
        run_id: str,
    ) -> int: ...

    def active_production_runs(self) -> list[DramaProductionRun]: ...


class DramaTimelineRendererPort(Protocol):
    def render_timeline(
        self,
        video_asset_ids: list[str],
        *,
        aspect_ratio: str,
        filename: str,
        subtitle_cues: list[dict[str, object]],
        audio_asset_ids: list[str | None],
        subtitle_style: dict[str, object],
        transition: str,
        transition_duration: float,
        music_asset_id: str | None,
        music_volume_db: float,
        ambience_asset_id: str | None,
        ambience_volume_db: float,
        ducking: bool,
        sound_effects: list[dict[str, object]],
    ) -> str: ...


class DramaAssetLookupPort(Protocol):
    def get(self, asset_id: str) -> dict[str, object]: ...


class DramaProductionMediaPort(Protocol):
    async def submit(self, request: dict[str, object]) -> dict[str, object]: ...

    def get(self, task_id: str) -> dict[str, object]: ...
