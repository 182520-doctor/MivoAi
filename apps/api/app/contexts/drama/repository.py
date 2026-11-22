"""SQLite persistence for short-drama project aggregates."""

from __future__ import annotations

import json

from app.contexts.drama.domain import (
    DramaAssetCandidate,
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
    DramaSceneContract,
    DramaShot,
    DramaShotEntityReference,
    DramaShotStatusEvent,
    DramaSoundEffect,
    DramaStageRevision,
    DramaSubtitleCue,
    DramaSubtitleStyle,
)
from app.infrastructure.persistence.database import Database


class DramaProjectRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def list_projects(self, limit: int = 100) -> list[DramaProject]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_projects
                ORDER BY updated_at DESC, rowid DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [_to_project(row) for row in rows]

    def get_project(self, project_id: str) -> DramaProject | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return _to_project(row) if row else None

    def create_project(
        self,
        *,
        project_id: str,
        title: str,
        idea: str,
        project_format: str,
        visual_style: str,
        workspace_path: str,
    ) -> DramaProject:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_projects
                    (id, title, idea, format, visual_style, status,
                     active_stage, workspace_path)
                VALUES (?, ?, ?, ?, ?, 'draft', 'brief', ?)
                """,
                (
                    project_id,
                    title,
                    idea,
                    project_format,
                    visual_style,
                    workspace_path,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧项目创建失败")
        return _to_project(row)

    def update_project_stage(
        self,
        project_id: str,
        *,
        active_stage: str,
        status: str | None = None,
    ) -> DramaProject | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_projects
                SET active_stage = ?,
                    status = COALESCE(?, status),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (active_stage, status, project_id),
            )
            row = connection.execute(
                "SELECT * FROM drama_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return _to_project(row) if row else None

    def list_documents(self, project_id: str) -> list[DramaDocument]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_documents
                WHERE project_id = ?
                ORDER BY kind, version DESC, rowid DESC
                """,
                (project_id,),
            ).fetchall()
        return [_to_document(row) for row in rows]

    def get_document(self, document_id: str) -> DramaDocument | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return _to_document(row) if row else None

    def create_document(
        self,
        *,
        document_id: str,
        project_id: str,
        kind: str,
        title: str,
        content: str,
    ) -> DramaDocument:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS version
                FROM drama_documents
                WHERE project_id = ? AND kind = ?
                """,
                (project_id, kind),
            ).fetchone()
            version = int(row["version"])
            connection.execute(
                """
                INSERT INTO drama_documents
                    (id, project_id, kind, version, status, title, content)
                VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    document_id,
                    project_id,
                    kind,
                    version,
                    title,
                    content,
                ),
            )
            created = connection.execute(
                "SELECT * FROM drama_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        if not created:
            raise RuntimeError("短剧文档创建失败")
        return _to_document(created)

    def update_document(
        self,
        document_id: str,
        *,
        title: str,
        content: str,
    ) -> DramaDocument | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_documents
                SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'draft'
                """,
                (title, content, document_id),
            )
            row = connection.execute(
                "SELECT * FROM drama_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return _to_document(row) if row else None

    def approve_document(self, document_id: str) -> DramaDocument | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_documents
                SET status = 'approved', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'draft'
                """,
                (document_id,),
            )
            row = connection.execute(
                "SELECT * FROM drama_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return _to_document(row) if row else None

    def list_episodes(self, project_id: str) -> list[DramaEpisode]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM drama_episodes
                WHERE project_id = ?
                ORDER BY episode_number ASC
                """,
                (project_id,),
            ).fetchall()
        return [_to_episode(row) for row in rows]

    def get_episode(self, episode_id: str) -> DramaEpisode | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def create_episode(
        self,
        *,
        episode_id: str,
        project_id: str,
        title: str,
        synopsis: str,
        plan: DramaEpisodePlan | None = None,
    ) -> DramaEpisode:
        resolved_plan = plan or DramaEpisodePlan()
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(episode_number), 0) + 1 AS number
                FROM drama_episodes WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            number = int(row["number"])
            connection.execute(
                """
                INSERT INTO drama_episodes
                    (id, project_id, episode_number, title, synopsis, plan_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    project_id,
                    number,
                    title,
                    synopsis,
                    json.dumps(
                        _episode_plan_payload(resolved_plan),
                        ensure_ascii=False,
                    ),
                ),
            )
            created = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        if not created:
            raise RuntimeError("短剧分集创建失败")
        return _to_episode(created)

    def update_episode_plan(
        self,
        episode_id: str,
        *,
        plan: DramaEpisodePlan,
    ) -> DramaEpisode | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_episodes
                SET plan_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(
                        _episode_plan_payload(plan),
                        ensure_ascii=False,
                    ),
                    episode_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def update_episode_export(
        self,
        episode_id: str,
        *,
        export_asset_id: str,
        export_manifest_id: str,
    ) -> DramaEpisode | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_episodes
                SET export_asset_id = ?,
                    export_manifest_id = ?,
                    status = 'rendered',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (export_asset_id, export_manifest_id, episode_id),
            )
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def create_export_manifest(
        self,
        *,
        manifest_id: str,
        project_id: str,
        episode_id: str,
        export_asset_id: str,
        manifest: dict[str, object],
    ) -> DramaExportManifest:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_export_manifests
                    (id, project_id, episode_id, export_asset_id,
                     manifest_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    manifest_id,
                    project_id,
                    episode_id,
                    export_asset_id,
                    json.dumps(manifest, ensure_ascii=False),
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_export_manifests WHERE id = ?",
                (manifest_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧导出清单创建失败")
        return _to_export_manifest(row)

    def list_export_manifests(
        self,
        episode_id: str,
    ) -> list[DramaExportManifest]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_export_manifests
                WHERE episode_id = ?
                ORDER BY created_at DESC, rowid DESC
                """,
                (episode_id,),
            ).fetchall()
        return [_to_export_manifest(row) for row in rows]

    def update_episode_subtitles(
        self,
        episode_id: str,
        *,
        cues: list[DramaSubtitleCue],
    ) -> DramaEpisode | None:
        payload = [
            {
                "startSeconds": cue.start_seconds,
                "endSeconds": cue.end_seconds,
                "text": cue.text,
            }
            for cue in cues
        ]
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_episodes
                SET subtitle_cues_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(payload, ensure_ascii=False), episode_id),
            )
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def update_episode_audio_mix(
        self,
        episode_id: str,
        *,
        audio_mix: DramaAudioMix,
    ) -> DramaEpisode | None:
        payload = {
            "soundEffects": [
                {
                    "assetId": effect.asset_id,
                    "startSeconds": effect.start_seconds,
                    "durationSeconds": effect.duration_seconds,
                    "volumeDb": effect.volume_db,
                }
                for effect in audio_mix.sound_effects
            ],
            "musicAssetId": audio_mix.music_asset_id,
            "musicVolumeDb": audio_mix.music_volume_db,
            "ambienceAssetId": audio_mix.ambience_asset_id,
            "ambienceVolumeDb": audio_mix.ambience_volume_db,
            "ducking": audio_mix.ducking,
        }
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_episodes
                SET audio_mix_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(payload, ensure_ascii=False),
                    episode_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def update_episode_subtitle_style(
        self,
        episode_id: str,
        *,
        subtitle_style: DramaSubtitleStyle,
    ) -> DramaEpisode | None:
        payload = {
            "preset": subtitle_style.preset,
            "fontSize": subtitle_style.font_size,
            "outline": subtitle_style.outline,
            "marginV": subtitle_style.margin_v,
            "primaryColor": subtitle_style.primary_color,
            "outlineColor": subtitle_style.outline_color,
        }
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_episodes
                SET subtitle_style_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(payload, ensure_ascii=False),
                    episode_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()
        return _to_episode(row) if row else None

    def list_scenes(self, episode_id: str) -> list[DramaScene]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM drama_scenes
                WHERE episode_id = ?
                ORDER BY scene_number ASC
                """,
                (episode_id,),
            ).fetchall()
        return [_to_scene(row) for row in rows]

    def get_scene(self, scene_id: str) -> DramaScene | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_scenes WHERE id = ?",
                (scene_id,),
            ).fetchone()
        return _to_scene(row) if row else None

    def create_scene(
        self,
        *,
        scene_id: str,
        episode_id: str,
        heading: str,
        summary: str,
        script_document_id: str | None,
    ) -> DramaScene:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(scene_number), 0) + 1 AS number
                FROM drama_scenes WHERE episode_id = ?
                """,
                (episode_id,),
            ).fetchone()
            number = int(row["number"])
            connection.execute(
                """
                INSERT INTO drama_scenes
                    (id, episode_id, scene_number, heading, summary,
                     script_document_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scene_id,
                    episode_id,
                    number,
                    heading,
                    summary,
                    script_document_id,
                ),
            )
            created = connection.execute(
                "SELECT * FROM drama_scenes WHERE id = ?",
                (scene_id,),
            ).fetchone()
        if not created:
            raise RuntimeError("短剧场次创建失败")
        return _to_scene(created)

    def list_shots(self, scene_id: str) -> list[DramaShot]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM drama_shots
                WHERE scene_id = ?
                ORDER BY shot_number ASC
                """,
                (scene_id,),
            ).fetchall()
        return [_to_shot(row) for row in rows]

    def get_shot(self, shot_id: str) -> DramaShot | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_shots WHERE id = ?",
                (shot_id,),
            ).fetchone()
        return _to_shot(row) if row else None

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
    ) -> DramaShot:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(shot_number), 0) + 1 AS number
                FROM drama_shots WHERE scene_id = ?
                """,
                (scene_id,),
            ).fetchone()
            number = int(row["number"])
            connection.execute(
                """
                INSERT INTO drama_shots
                    (id, scene_id, shot_number, title, description,
                     dialogue, duration_seconds, direction_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shot_id,
                    scene_id,
                    number,
                    title,
                    description,
                    dialogue,
                    duration_seconds,
                    json.dumps(direction or {}, ensure_ascii=False),
                ),
            )
            created = connection.execute(
                "SELECT * FROM drama_shots WHERE id = ?",
                (shot_id,),
            ).fetchone()
        if not created:
            raise RuntimeError("短剧镜头创建失败")
        return _to_shot(created)

    def update_shot_status(
        self,
        shot_id: str,
        *,
        status: str,
    ) -> DramaShot | None:
        return self.update_shot(shot_id, status=status)

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
    ) -> DramaShot | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_shots
                SET status = COALESCE(?, status),
                    first_frame_asset_id = COALESCE(?, first_frame_asset_id),
                    last_frame_asset_id = COALESCE(?, last_frame_asset_id),
                    grid9_asset_id = COALESCE(?, grid9_asset_id),
                    storyboard_asset_id = COALESCE(
                        ?, storyboard_asset_id
                    ),
                    video_asset_id = COALESCE(?, video_asset_id),
                    audio_asset_id = COALESCE(?, audio_asset_id),
                    direction_json = COALESCE(?, direction_json),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    first_frame_asset_id,
                    last_frame_asset_id,
                    grid9_asset_id,
                    storyboard_asset_id,
                    video_asset_id,
                    audio_asset_id,
                    (
                        json.dumps(direction, ensure_ascii=False)
                        if direction is not None
                        else None
                    ),
                    shot_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_shots WHERE id = ?",
                (shot_id,),
            ).fetchone()
        return _to_shot(row) if row else None

    def update_shot_prompt(
        self,
        shot_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> DramaShot | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT prompt_overrides_json FROM drama_shots WHERE id = ?",
                (shot_id,),
            ).fetchone()
            if not row:
                return None
            prompts = json.loads(row["prompt_overrides_json"] or "{}")
            normalized = prompt.strip()
            if normalized:
                prompts[slot] = normalized
            else:
                prompts.pop(slot, None)
            connection.execute(
                """
                UPDATE drama_shots
                SET prompt_overrides_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(prompts, ensure_ascii=False),
                    shot_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM drama_shots WHERE id = ?",
                (shot_id,),
            ).fetchone()
        return _to_shot(updated) if updated else None

    def create_shot_status_event(
        self,
        *,
        event_id: str,
        shot_id: str,
        from_status: str,
        to_status: str,
        reviewer: str,
        note: str,
    ) -> DramaShotStatusEvent:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_shot_status_events
                    (id, shot_id, from_status, to_status, reviewer, note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    shot_id,
                    from_status,
                    to_status,
                    reviewer,
                    note,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_shot_status_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("镜头状态事件创建失败")
        return _to_shot_status_event(row)

    def list_shot_status_events(
        self,
        shot_id: str,
        *,
        limit: int = 50,
    ) -> list[DramaShotStatusEvent]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_shot_status_events
                WHERE shot_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (shot_id, max(1, min(limit, 200))),
            ).fetchall()
        return [_to_shot_status_event(row) for row in rows]

    def list_entities(self, project_id: str) -> list[DramaEntity]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM drama_entities
                WHERE project_id = ?
                ORDER BY kind, created_at, rowid
                """,
                (project_id,),
            ).fetchall()
        return [_to_entity(row) for row in rows]

    def get_entity(self, entity_id: str) -> DramaEntity | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        return _to_entity(row) if row else None

    def create_entity(
        self,
        *,
        entity_id: str,
        project_id: str,
        kind: str,
        name: str,
        description: str,
        profile: dict[str, str] | None = None,
    ) -> DramaEntity:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_entities
                    (id, project_id, kind, name, description, profile_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    project_id,
                    kind,
                    name,
                    description,
                    json.dumps(profile or {}, ensure_ascii=False),
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧实体创建失败")
        return _to_entity(row)

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
    ) -> DramaEntity | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_entities
                SET name = ?, description = ?, status = ?,
                    primary_asset_id = ?, reference_asset_ids_json = ?,
                    asset_slots_json = ?,
                    profile_json = ?,
                    voice_name = ?, voice_rate = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    name,
                    description,
                    status,
                    primary_asset_id,
                    json.dumps(reference_asset_ids, ensure_ascii=False),
                    json.dumps(asset_slots or {}, ensure_ascii=False),
                    json.dumps(profile or {}, ensure_ascii=False),
                    voice_name,
                    voice_rate,
                    entity_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        return _to_entity(row) if row else None

    def update_entity_prompt(
        self,
        entity_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> DramaEntity | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT asset_prompts_json FROM drama_entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
            if not row:
                return None
            prompts = json.loads(row["asset_prompts_json"] or "{}")
            normalized = prompt.strip()
            if normalized:
                prompts[slot] = normalized
            else:
                prompts.pop(slot, None)
            connection.execute(
                """
                UPDATE drama_entities
                SET asset_prompts_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(prompts, ensure_ascii=False),
                    entity_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM drama_entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        return _to_entity(updated) if updated else None

    def list_shot_references(
        self,
        shot_id: str,
    ) -> list[DramaShotEntityReference]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT shot_id, entity_id, role
                FROM drama_shot_entities
                WHERE shot_id = ?
                ORDER BY role, entity_id
                """,
                (shot_id,),
            ).fetchall()
        return [_to_shot_reference(row) for row in rows]

    def list_reviews(
        self,
        project_id: str,
        *,
        stage: str | None = None,
    ) -> list[DramaReview]:
        query = """
            SELECT *
            FROM drama_reviews
            WHERE project_id = ?
        """
        parameters: list[object] = [project_id]
        if stage:
            query += " AND stage = ?"
            parameters.append(stage)
        query += " ORDER BY created_at ASC, rowid ASC"
        with self._database.transaction() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_to_review(row) for row in rows]

    def list_asset_candidates(
        self,
        project_id: str,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        slot: str | None = None,
    ) -> list[DramaAssetCandidate]:
        query = """
            SELECT *
            FROM drama_asset_candidates
            WHERE project_id = ?
        """
        parameters: list[object] = [project_id]
        if subject_type:
            query += " AND subject_type = ?"
            parameters.append(subject_type)
        if subject_id:
            query += " AND subject_id = ?"
            parameters.append(subject_id)
        if slot:
            query += " AND slot = ?"
            parameters.append(slot)
        query += """
            ORDER BY
                CASE status
                    WHEN 'selected' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'superseded' THEN 2
                    ELSE 3
                END,
                updated_at DESC,
                rowid DESC
        """
        with self._database.transaction() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_to_asset_candidate(row) for row in rows]

    def get_asset_candidate(
        self,
        candidate_id: str,
    ) -> DramaAssetCandidate | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_asset_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return _to_asset_candidate(row) if row else None

    def record_asset_candidate(
        self,
        *,
        candidate_id: str,
        project_id: str,
        subject_type: str,
        subject_id: str,
        slot: str,
        asset_id: str,
        source: str = "binding",
    ) -> DramaAssetCandidate:
        with self._database.transaction() as connection:
            if not (subject_type == "entity" and slot == "reference"):
                connection.execute(
                    """
                    UPDATE drama_asset_candidates
                    SET status = 'superseded',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE subject_type = ?
                      AND subject_id = ?
                      AND slot = ?
                      AND asset_id <> ?
                      AND status = 'selected'
                    """,
                    (subject_type, subject_id, slot, asset_id),
                )
            existing = connection.execute(
                """
                SELECT id
                FROM drama_asset_candidates
                WHERE subject_type = ?
                  AND subject_id = ?
                  AND slot = ?
                  AND asset_id = ?
                """,
                (subject_type, subject_id, slot, asset_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE drama_asset_candidates
                    SET status = 'selected',
                        source = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (source, existing["id"]),
                )
                candidate_id = str(existing["id"])
            else:
                connection.execute(
                    """
                    INSERT INTO drama_asset_candidates
                        (id, project_id, subject_type, subject_id, slot,
                         asset_id, status, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'selected', ?)
                    """,
                    (
                        candidate_id,
                        project_id,
                        subject_type,
                        subject_id,
                        slot,
                        asset_id,
                        source,
                    ),
                )
            row = connection.execute(
                "SELECT * FROM drama_asset_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧候选素材保存失败")
        return _to_asset_candidate(row)

    def update_asset_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
    ) -> DramaAssetCandidate | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_asset_candidates
                SET status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, candidate_id),
            )
            row = connection.execute(
                "SELECT * FROM drama_asset_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return _to_asset_candidate(row) if row else None

    def list_production_runs(
        self,
        project_id: str,
        *,
        episode_id: str | None = None,
        limit: int = 50,
    ) -> list[DramaProductionRun]:
        query = """
            SELECT *
            FROM drama_production_runs
            WHERE project_id = ?
        """
        parameters: list[object] = [project_id]
        if episode_id:
            query += " AND episode_id = ?"
            parameters.append(episode_id)
        query += " ORDER BY updated_at DESC, rowid DESC LIMIT ?"
        parameters.append(max(1, min(limit, 200)))
        with self._database.transaction() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_to_production_run(row) for row in rows]

    def get_production_run(
        self,
        run_id: str,
    ) -> DramaProductionRun | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM drama_production_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return _to_production_run(row) if row else None

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
        planning: dict[str, object] | None = None,
    ) -> DramaProductionRun:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_production_runs
                    (id, project_id, episode_id, stage, name, status,
                     requires_approval, max_parallel, plan_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    episode_id,
                    stage,
                    name,
                    status,
                    1 if requires_approval else 0,
                    max_parallel,
                    json.dumps(planning or {}, ensure_ascii=False),
                ),
            )
            connection.executemany(
                """
                INSERT INTO drama_production_run_items
                    (id, run_id, position, target_type, target_id, slot,
                     title, status, request_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                [
                    (
                        str(item["id"]),
                        run_id,
                        int(item["position"]),
                        str(item["targetType"]),
                        str(item["targetId"]),
                        str(item["slot"]),
                        str(item.get("title") or ""),
                        json.dumps(
                            item.get("request") or {},
                            ensure_ascii=False,
                        ),
                    )
                    for item in items
                ],
            )
            row = connection.execute(
                "SELECT * FROM drama_production_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧制作运行创建失败")
        return _to_production_run(row)

    def update_production_run_status(
        self,
        run_id: str,
        *,
        status: str,
        approved_by: str | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> DramaProductionRun | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_production_runs
                SET status = ?,
                    approved_by = COALESCE(?, approved_by),
                    started_at = CASE
                        WHEN ? THEN COALESCE(started_at, CURRENT_TIMESTAMP)
                        ELSE started_at
                    END,
                    completed_at = CASE
                        WHEN ? THEN CURRENT_TIMESTAMP
                        WHEN ? IN ('queued', 'running') THEN NULL
                        ELSE completed_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    approved_by,
                    1 if started else 0,
                    1 if completed else 0,
                    status,
                    run_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_production_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return _to_production_run(row) if row else None

    def list_production_run_items(
        self,
        run_id: str,
    ) -> list[DramaProductionRunItem]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_production_run_items
                WHERE run_id = ?
                ORDER BY position ASC
                """,
                (run_id,),
            ).fetchall()
        return [_to_production_run_item(row) for row in rows]

    def update_production_run_item(
        self,
        item_id: str,
        *,
        status: str,
        generation_task_id: str | None = None,
        result_asset_id: str | None = None,
        error: str | None = None,
    ) -> DramaProductionRunItem | None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE drama_production_run_items
                SET status = ?,
                    generation_task_id = COALESCE(
                        ?, generation_task_id
                    ),
                    result_asset_id = COALESCE(?, result_asset_id),
                    error = COALESCE(?, error),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    generation_task_id,
                    result_asset_id,
                    error,
                    item_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_production_run_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _to_production_run_item(row) if row else None

    def reset_failed_production_run_items(self, run_id: str) -> int:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE drama_production_run_items
                SET status = 'pending',
                    generation_task_id = NULL,
                    result_asset_id = NULL,
                    error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND status = 'failed'
                """,
                (run_id,),
            )
            return cursor.rowcount

    def active_production_runs(self) -> list[DramaProductionRun]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM drama_production_runs
                WHERE status IN ('queued', 'running')
                ORDER BY updated_at ASC
                """
            ).fetchall()
        return [_to_production_run(row) for row in rows]

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
    ) -> DramaReview:
        payload = [
            {
                "key": item.key,
                "label": item.label,
                "passed": item.passed,
                "note": item.note,
            }
            for item in checklist
        ]
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO drama_reviews
                    (id, project_id, stage, role_id, status, score,
                     checklist_json, feedback, reviewer, artifact_revision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    project_id,
                    stage,
                    role_id,
                    status,
                    score,
                    json.dumps(payload, ensure_ascii=False),
                    feedback,
                    reviewer,
                    artifact_revision,
                ),
            )
            row = connection.execute(
                "SELECT * FROM drama_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧审核记录创建失败")
        return _to_review(row)

    def get_stage_revision(
        self,
        project_id: str,
        stage: str,
    ) -> DramaStageRevision:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO drama_stage_revisions
                    (project_id, stage)
                VALUES (?, ?)
                """,
                (project_id, stage),
            )
            row = connection.execute(
                """
                SELECT *
                FROM drama_stage_revisions
                WHERE project_id = ? AND stage = ?
                """,
                (project_id, stage),
            ).fetchone()
            if (
                row
                and row["approved_revision"] is None
                and int(row["revision"]) == 0
            ):
                decision = connection.execute(
                    """
                    SELECT status, created_at
                    FROM drama_reviews
                    WHERE project_id = ?
                      AND stage = ?
                      AND role_id = 'stage_gate'
                      AND reviewer = 'user'
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT 1
                    """,
                    (project_id, stage),
                ).fetchone()
                if decision and decision["status"] == "passed":
                    connection.execute(
                        """
                        UPDATE drama_stage_revisions
                        SET approved_revision = 0,
                            approved_by = 'migration',
                            approved_at = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE project_id = ? AND stage = ?
                        """,
                        (
                            decision["created_at"],
                            project_id,
                            stage,
                        ),
                    )
                    row = connection.execute(
                        """
                        SELECT *
                        FROM drama_stage_revisions
                        WHERE project_id = ? AND stage = ?
                        """,
                        (project_id, stage),
                    ).fetchone()
        if not row:
            raise RuntimeError("短剧阶段修订读取失败")
        return _to_stage_revision(row)

    def touch_stage_revisions(
        self,
        project_id: str,
        *,
        stages: list[str],
        reason: str,
    ) -> None:
        with self._database.transaction() as connection:
            for stage in dict.fromkeys(stages):
                connection.execute(
                    """
                    INSERT INTO drama_stage_revisions
                        (project_id, stage, revision, last_change_reason)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(project_id, stage) DO UPDATE SET
                        revision = revision + 1,
                        last_change_reason = excluded.last_change_reason,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (project_id, stage, reason),
                )

    def set_stage_approval(
        self,
        project_id: str,
        *,
        stage: str,
        approved: bool,
        approved_by: str,
    ) -> DramaStageRevision:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO drama_stage_revisions
                    (project_id, stage)
                VALUES (?, ?)
                """,
                (project_id, stage),
            )
            connection.execute(
                """
                UPDATE drama_stage_revisions
                SET approved_revision = CASE
                        WHEN ? THEN revision
                        ELSE NULL
                    END,
                    approved_by = CASE
                        WHEN ? THEN ?
                        ELSE NULL
                    END,
                    approved_at = CASE
                        WHEN ? THEN CURRENT_TIMESTAMP
                        ELSE NULL
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND stage = ?
                """,
                (
                    1 if approved else 0,
                    1 if approved else 0,
                    approved_by,
                    1 if approved else 0,
                    project_id,
                    stage,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM drama_stage_revisions
                WHERE project_id = ? AND stage = ?
                """,
                (project_id, stage),
            ).fetchone()
        if not row:
            raise RuntimeError("短剧阶段审批状态保存失败")
        return _to_stage_revision(row)

    def replace_shot_references(
        self,
        shot_id: str,
        references: list[tuple[str, str]],
    ) -> list[DramaShotEntityReference]:
        with self._database.transaction() as connection:
            connection.execute(
                "DELETE FROM drama_shot_entities WHERE shot_id = ?",
                (shot_id,),
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO drama_shot_entities
                    (shot_id, entity_id, role)
                VALUES (?, ?, ?)
                """,
                [(shot_id, entity_id, role) for entity_id, role in references],
            )
            rows = connection.execute(
                """
                SELECT shot_id, entity_id, role
                FROM drama_shot_entities
                WHERE shot_id = ?
                ORDER BY role, entity_id
                """,
                (shot_id,),
            ).fetchall()
        return [_to_shot_reference(row) for row in rows]


def _to_project(row) -> DramaProject:
    return DramaProject(
        id=row["id"],
        title=row["title"],
        idea=row["idea"],
        format=row["format"],
        visual_style=row["visual_style"],
        status=row["status"],
        active_stage=row["active_stage"],
        workspace_path=row["workspace_path"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_document(row) -> DramaDocument:
    return DramaDocument(
        id=row["id"],
        project_id=row["project_id"],
        kind=row["kind"],
        version=row["version"],
        status=row["status"],
        title=row["title"],
        content=row["content"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_episode(row) -> DramaEpisode:
    cues = json.loads(row["subtitle_cues_json"] or "[]")
    subtitle_style = json.loads(row["subtitle_style_json"] or "{}")
    audio_mix = json.loads(row["audio_mix_json"] or "{}")
    plan = json.loads(row["plan_json"] or "{}")
    return DramaEpisode(
        id=row["id"],
        project_id=row["project_id"],
        episode_number=row["episode_number"],
        title=row["title"],
        synopsis=row["synopsis"],
        status=row["status"],
        export_asset_id=row["export_asset_id"],
        export_manifest_id=row["export_manifest_id"],
        subtitle_cues=tuple(
            DramaSubtitleCue(
                start_seconds=float(cue.get("startSeconds") or 0),
                end_seconds=float(cue.get("endSeconds") or 0),
                text=str(cue.get("text") or ""),
            )
            for cue in cues
        ),
        subtitle_style=DramaSubtitleStyle(
            preset=str(subtitle_style.get("preset", "short_video")),
            font_size=int(subtitle_style.get("fontSize", 30)),
            outline=float(subtitle_style.get("outline", 2)),
            margin_v=int(subtitle_style.get("marginV", 96)),
            primary_color=str(
                subtitle_style.get("primaryColor", "#FFFFFF")
            ),
            outline_color=str(
                subtitle_style.get("outlineColor", "#101010")
            ),
        ),
        audio_mix=DramaAudioMix(
            sound_effects=tuple(
                DramaSoundEffect(
                    asset_id=str(effect.get("assetId") or ""),
                    start_seconds=float(
                        effect.get("startSeconds") or 0
                    ),
                    duration_seconds=float(
                        effect.get("durationSeconds") or 0
                    ),
                    volume_db=float(effect.get("volumeDb") or 0),
                )
                for effect in audio_mix.get("soundEffects", [])
                if effect.get("assetId")
            ),
            music_asset_id=audio_mix.get("musicAssetId"),
            music_volume_db=float(
                audio_mix.get("musicVolumeDb", -18.0)
            ),
            ambience_asset_id=audio_mix.get("ambienceAssetId"),
            ambience_volume_db=float(
                audio_mix.get("ambienceVolumeDb", -22.0)
            ),
            ducking=bool(audio_mix.get("ducking", True)),
        ),
        plan=_episode_plan_from_payload(plan),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_export_manifest(row) -> DramaExportManifest:
    return DramaExportManifest(
        id=row["id"],
        project_id=row["project_id"],
        episode_id=row["episode_id"],
        export_asset_id=row["export_asset_id"],
        manifest=json.loads(row["manifest_json"] or "{}"),
        created_at=row["created_at"],
    )


def _to_scene(row) -> DramaScene:
    return DramaScene(
        id=row["id"],
        episode_id=row["episode_id"],
        scene_number=row["scene_number"],
        heading=row["heading"],
        summary=row["summary"],
        script_document_id=row["script_document_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_shot(row) -> DramaShot:
    return DramaShot(
        id=row["id"],
        scene_id=row["scene_id"],
        shot_number=row["shot_number"],
        title=row["title"],
        description=row["description"],
        dialogue=row["dialogue"],
        duration_seconds=row["duration_seconds"],
        status=row["status"],
        first_frame_asset_id=row["first_frame_asset_id"],
        last_frame_asset_id=row["last_frame_asset_id"],
        grid9_asset_id=row["grid9_asset_id"],
        storyboard_asset_id=row["storyboard_asset_id"],
        video_asset_id=row["video_asset_id"],
        audio_asset_id=row["audio_asset_id"],
        prompt_overrides=json.loads(row["prompt_overrides_json"] or "{}"),
        direction=json.loads(row["direction_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_shot_status_event(row) -> DramaShotStatusEvent:
    return DramaShotStatusEvent(
        id=row["id"],
        shot_id=row["shot_id"],
        from_status=row["from_status"],
        to_status=row["to_status"],
        reviewer=row["reviewer"],
        note=row["note"],
        created_at=row["created_at"],
    )


def _to_entity(row) -> DramaEntity:
    return DramaEntity(
        id=row["id"],
        project_id=row["project_id"],
        kind=row["kind"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        primary_asset_id=row["primary_asset_id"],
        reference_asset_ids=tuple(
            json.loads(row["reference_asset_ids_json"] or "[]")
        ),
        asset_slots=json.loads(row["asset_slots_json"] or "{}"),
        asset_prompts=json.loads(row["asset_prompts_json"] or "{}"),
        profile=json.loads(row["profile_json"] or "{}"),
        voice_name=row["voice_name"],
        voice_rate=row["voice_rate"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_shot_reference(row) -> DramaShotEntityReference:
    return DramaShotEntityReference(
        shot_id=row["shot_id"],
        entity_id=row["entity_id"],
        role=row["role"],
    )


def _to_review(row) -> DramaReview:
    checklist = json.loads(row["checklist_json"] or "[]")
    return DramaReview(
        id=row["id"],
        project_id=row["project_id"],
        stage=row["stage"],
        role_id=row["role_id"],
        status=row["status"],
        score=float(row["score"]),
        checklist=tuple(
            DramaReviewCheck(
                key=str(item.get("key") or ""),
                label=str(item.get("label") or ""),
                passed=bool(item.get("passed")),
                note=str(item.get("note") or ""),
            )
            for item in checklist
        ),
        feedback=row["feedback"],
        reviewer=row["reviewer"],
        artifact_revision=int(row["artifact_revision"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_stage_revision(row) -> DramaStageRevision:
    return DramaStageRevision(
        project_id=row["project_id"],
        stage=row["stage"],
        revision=int(row["revision"]),
        approved_revision=(
            int(row["approved_revision"])
            if row["approved_revision"] is not None
            else None
        ),
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        last_change_reason=row["last_change_reason"],
        updated_at=row["updated_at"],
    )


def _to_asset_candidate(row) -> DramaAssetCandidate:
    return DramaAssetCandidate(
        id=row["id"],
        project_id=row["project_id"],
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        slot=row["slot"],
        asset_id=row["asset_id"],
        status=row["status"],
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_production_run(row) -> DramaProductionRun:
    return DramaProductionRun(
        id=row["id"],
        project_id=row["project_id"],
        episode_id=row["episode_id"],
        stage=row["stage"],
        name=row["name"],
        status=row["status"],
        requires_approval=bool(row["requires_approval"]),
        max_parallel=int(row["max_parallel"]),
        approved_by=row["approved_by"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        planning=json.loads(row["plan_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_production_run_item(row) -> DramaProductionRunItem:
    return DramaProductionRunItem(
        id=row["id"],
        run_id=row["run_id"],
        position=int(row["position"]),
        target_type=row["target_type"],
        target_id=row["target_id"],
        slot=row["slot"],
        title=row["title"],
        status=row["status"],
        generation_task_id=row["generation_task_id"],
        result_asset_id=row["result_asset_id"],
        error=row["error"],
        request=json.loads(row["request_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _episode_plan_payload(plan: DramaEpisodePlan) -> dict[str, object]:
    return {
        "timeScope": plan.time_scope,
        "locations": list(plan.locations),
        "interiorExterior": list(plan.interior_exterior),
        "characters": list(plan.characters),
        "scenes": list(plan.scenes),
        "storyBeats": list(plan.story_beats),
        "visualRequirements": list(plan.visual_requirements),
        "dialogueRequirements": list(plan.dialogue_requirements),
        "continuityRisks": list(plan.continuity_risks),
        "sceneContracts": [
            {
                "sceneNumber": item.scene_number,
                "title": item.title,
                "valueIn": item.value_in,
                "characterObjectives": list(item.character_objectives),
                "obstacle": item.obstacle,
                "tactics": list(item.tactics),
                "beats": list(item.beats),
                "turn": item.turn,
                "valueOut": item.value_out,
                "subtext": item.subtext,
                "visualStrategy": item.visual_strategy,
                "performanceNotes": item.performance_notes,
                "soundNotes": item.sound_notes,
            }
            for item in plan.scene_contracts
        ],
    }


def _episode_plan_from_payload(
    payload: dict[str, object],
) -> DramaEpisodePlan:
    return DramaEpisodePlan(
        time_scope=str(payload.get("timeScope") or ""),
        locations=tuple(str(value) for value in payload.get("locations") or []),
        interior_exterior=tuple(
            str(value) for value in payload.get("interiorExterior") or []
        ),
        characters=tuple(
            str(value) for value in payload.get("characters") or []
        ),
        scenes=tuple(str(value) for value in payload.get("scenes") or []),
        story_beats=tuple(
            str(value) for value in payload.get("storyBeats") or []
        ),
        visual_requirements=tuple(
            str(value) for value in payload.get("visualRequirements") or []
        ),
        dialogue_requirements=tuple(
            str(value) for value in payload.get("dialogueRequirements") or []
        ),
        continuity_risks=tuple(
            str(value) for value in payload.get("continuityRisks") or []
        ),
        scene_contracts=tuple(
            DramaSceneContract(
                scene_number=int(item.get("sceneNumber") or 0),
                title=str(item.get("title") or ""),
                value_in=str(item.get("valueIn") or ""),
                character_objectives=tuple(
                    str(value)
                    for value in item.get("characterObjectives") or []
                ),
                obstacle=str(item.get("obstacle") or ""),
                tactics=tuple(
                    str(value) for value in item.get("tactics") or []
                ),
                beats=tuple(
                    str(value) for value in item.get("beats") or []
                ),
                turn=str(item.get("turn") or ""),
                value_out=str(item.get("valueOut") or ""),
                subtext=str(item.get("subtext") or ""),
                visual_strategy=str(item.get("visualStrategy") or ""),
                performance_notes=str(
                    item.get("performanceNotes") or ""
                ),
                sound_notes=str(item.get("soundNotes") or ""),
            )
            for item in payload.get("sceneContracts") or []
            if isinstance(item, dict) and int(item.get("sceneNumber") or 0) > 0
        ),
    )
