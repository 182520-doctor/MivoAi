"""Short-drama project use cases."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.modules.drama.domain import (
    DRAMA_CANDIDATE_STATUSES,
    DRAMA_CANDIDATE_SUBJECT_TYPES,
    DRAMA_DOCUMENT_KINDS,
    DRAMA_ENTITY_KINDS,
    DRAMA_PRODUCTION_ROLES,
    DRAMA_REVIEW_STATUSES,
    DRAMA_RUN_ITEM_STATUSES,
    DRAMA_STAGE_OWNERS,
    DRAMA_STAGES,
    DramaAudioMix,
    DramaDocument,
    DramaEpisode,
    DramaEpisodePlan,
    DramaProject,
    DramaReview,
    DramaReviewCheck,
    DramaSceneContract,
    DramaSoundEffect,
    DramaSubtitleCue,
    DramaSubtitleStyle,
)
from app.modules.drama.ports import (
    DramaAssetLookupPort,
    DramaProductionMediaPort,
    DramaProjectRepositoryPort,
    DramaTimelineRendererPort,
    DramaWorkspacePort,
)
from app.shared.errors import ProviderConfigurationError


class DramaProjectService:
    def __init__(
        self,
        repository: DramaProjectRepositoryPort,
        workspace_manager: DramaWorkspacePort,
        timeline_renderer: DramaTimelineRendererPort,
        assets: DramaAssetLookupPort,
        production_media: DramaProductionMediaPort | None = None,
    ) -> None:
        self._repository = repository
        self._workspace_manager = workspace_manager
        self._timeline_renderer = timeline_renderer
        self._assets = assets
        self._production_media = production_media
        self._run_tasks: set[asyncio.Task[None]] = set()

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            _project_view(project)
            for project in self._repository.list_projects(limit)
        ]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        project = self._repository.get_project(project_id)
        return _project_view(project) if project else None

    def roles(self, *, stage: str | None = None) -> list[dict[str, Any]]:
        roles = [
            role
            for role in DRAMA_PRODUCTION_ROLES
            if not stage or stage in role.stage_ids
        ]
        return [_role_view(role) for role in roles]

    def production_control(self, project_id: str) -> dict[str, Any]:
        project = self._repository.get_project(project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        reviews = self._repository.list_reviews(project_id)
        episodes = self._repository.list_episodes(project_id)
        revisions = {
            stage: self._repository.get_stage_revision(project_id, stage)
            for stage in DRAMA_STAGES
        }
        gates = [
            _stage_gate_view(
                stage,
                reviews=[
                    review for review in reviews if review.stage == stage
                ],
                current_revision=revisions[stage].revision,
                approved_revision=revisions[stage].approved_revision,
                last_change_reason=revisions[stage].last_change_reason,
            )
            for stage in DRAMA_STAGES
        ]
        return {
            "project": _project_view(project),
            "roles": [_role_view(role) for role in DRAMA_PRODUCTION_ROLES],
            "currentStage": next(
                (
                    gate
                    for gate in gates
                    if gate["stage"] == project.active_stage
                ),
                gates[0],
            ),
            "gates": gates,
            "episodes": [
                {
                    "id": episode.id,
                    "episodeNumber": episode.episode_number,
                    "title": episode.title,
                    "synopsis": episode.synopsis,
                    "plan": _episode_plan_view(episode.plan),
                    "planComplete": _episode_plan_complete(episode.plan),
                }
                for episode in episodes
            ],
        }

    def series_production(self, project_id: str) -> dict[str, Any]:
        project = self._repository.get_project(project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        control = self.production_control(project_id)
        plans = {
            episode["id"]: episode["planComplete"]
            for episode in control["episodes"]
        }
        entities = {
            entity.id: entity
            for entity in self._repository.list_entities(project_id)
        }
        runs = self._repository.list_production_runs(project_id, limit=200)
        episodes: list[dict[str, Any]] = []
        totals = {
            "episodes": 0,
            "plansComplete": 0,
            "scenes": 0,
            "shots": 0,
            "keyframesReady": 0,
            "videosReady": 0,
            "shotsApproved": 0,
            "episodesRendered": 0,
            "episodesAwaitingApproval": 0,
            "episodesRunning": 0,
            "episodesNeedingRetry": 0,
            "episodesReadyToAdvance": 0,
        }
        for episode in self.production(project_id):
            shots = [
                shot
                for scene in episode.get("scenes") or []
                for shot in scene.get("shots") or []
            ]
            scene_count = len(episode.get("scenes") or [])
            keyframes_ready = sum(
                bool(shot.get("firstFrameAssetId"))
                or bool(shot.get("storyboardAssetId"))
                for shot in shots
            )
            videos_ready = sum(
                bool(shot.get("videoAssetId")) for shot in shots
            )
            shots_approved = sum(
                shot.get("status") == "approved" for shot in shots
            )
            missing_keyframes = [
                {"id": shot["id"], "title": shot.get("title") or "未命名镜头"}
                for shot in shots
                if not shot.get("firstFrameAssetId")
                and not shot.get("storyboardAssetId")
            ]
            missing_videos = [
                {"id": shot["id"], "title": shot.get("title") or "未命名镜头"}
                for shot in shots
                if not shot.get("videoAssetId")
            ]
            unreviewed_shots = [
                {"id": shot["id"], "title": shot.get("title") or "未命名镜头"}
                for shot in shots
                if shot.get("status") != "approved"
            ]
            referenced_entity_ids = {
                str(reference.get("entityId"))
                for shot in shots
                for reference in shot.get("entityReferences") or []
                if reference.get("entityId")
            }
            referenced_entities = [
                entities[entity_id]
                for entity_id in referenced_entity_ids
                if entity_id in entities
            ]
            assets_ready = sum(
                bool(entity.primary_asset_id)
                for entity in referenced_entities
            )
            assets_locked = sum(
                entity.status == "locked" for entity in referenced_entities
            )
            plan_complete = bool(plans.get(episode["id"]))
            rendered = bool(episode.get("exportAssetId")) or (
                episode.get("status") == "rendered"
            )
            if not plan_complete:
                next_action = "complete_plan"
                next_action_label = "补齐分集计划"
            elif not shots:
                next_action = "breakdown"
                next_action_label = "拆解场次与镜头"
            elif keyframes_ready < len(shots):
                next_action = "generate_keyframes"
                next_action_label = f"补齐 {len(shots) - keyframes_ready} 个关键帧"
            elif videos_ready < len(shots):
                next_action = "generate_videos"
                next_action_label = f"生成 {len(shots) - videos_ready} 条镜头视频"
            elif shots_approved < len(shots):
                next_action = "review_shots"
                next_action_label = (
                    f"审核 {len(shots) - shots_approved} 条镜头视频"
                )
            elif not rendered:
                next_action = "render_episode"
                next_action_label = "合成整集成片"
            else:
                next_action = "completed"
                next_action_label = "本集视频已完成"
            latest_run = next(
                (
                    run
                    for run in runs
                    if run.episode_id == episode["id"]
                ),
                None,
            )
            if latest_run and latest_run.status in {
                "draft",
                "awaiting_approval",
            }:
                queue_state = "awaiting_approval"
                queue_label = f"{latest_run.stage} 批次待确认"
            elif latest_run and latest_run.status in {"queued", "running"}:
                queue_state = "running"
                queue_label = f"{latest_run.stage} 批次执行中"
            elif latest_run and latest_run.status in {"partial", "failed"}:
                queue_state = "needs_retry"
                queue_label = f"{latest_run.stage} 批次需要处理"
            elif next_action in {"complete_plan", "breakdown"}:
                queue_state = "blocked"
                queue_label = "等待补齐分集结构"
            elif next_action == "completed":
                queue_state = "completed"
                queue_label = "本集视频已完成"
            else:
                queue_state = "ready"
                queue_label = next_action_label
            if referenced_entity_ids and (
                assets_ready < len(referenced_entity_ids)
                or assets_locked < len(referenced_entity_ids)
            ):
                assets_status = (
                    "pending"
                    if assets_ready < len(referenced_entity_ids)
                    else "changes_requested"
                )
                assets_label = (
                    f"{assets_ready}/{len(referenced_entity_ids)} 主资产就绪 · "
                    f"{assets_locked}/{len(referenced_entity_ids)} 已锁定"
                )
            else:
                assets_status = "approved" if referenced_entity_ids else "pending"
                assets_label = (
                    f"{assets_locked}/{len(referenced_entity_ids)} 资产已锁定"
                    if referenced_entity_ids
                    else "未绑定角色、场景或道具"
                )
            episodes.append(
                {
                    "id": episode["id"],
                    "episodeNumber": episode["episodeNumber"],
                    "title": episode["title"],
                    "synopsis": episode.get("synopsis") or "",
                    "status": episode.get("status"),
                    "planComplete": plan_complete,
                    "sceneCount": scene_count,
                    "shotCount": len(shots),
                    "keyframesReady": keyframes_ready,
                    "videosReady": videos_ready,
                    "shotsApproved": shots_approved,
                    "rendered": rendered,
                    "nextAction": next_action,
                    "nextActionLabel": next_action_label,
                    "queueState": queue_state,
                    "queueLabel": queue_label,
                    "missingKeyframes": missing_keyframes,
                    "missingVideos": missing_videos,
                    "unreviewedShots": unreviewed_shots,
                    "assetCoverage": {
                        "referenced": len(referenced_entity_ids),
                        "ready": assets_ready,
                        "locked": assets_locked,
                    },
                    "gates": {
                        "breakdown": {
                            "status": (
                                "approved"
                                if plan_complete and scene_count and shots
                                else "pending"
                            ),
                            "label": (
                                f"{scene_count} 场 · {len(shots)} 镜"
                                if plan_complete and scene_count and shots
                                else "分集计划或镜头清单未完成"
                            ),
                            "approved": bool(
                                plan_complete and scene_count and shots
                            ),
                        },
                        "assets": {
                            "status": assets_status,
                            "label": assets_label,
                            "approved": assets_status == "approved",
                        },
                        "keyframes": {
                            "status": (
                                "approved"
                                if shots and keyframes_ready == len(shots)
                                else "pending"
                            ),
                            "label": (
                                f"{keyframes_ready}/{len(shots)} 镜头有关键帧"
                            ),
                            "approved": bool(
                                shots and keyframes_ready == len(shots)
                            ),
                        },
                        "clips": {
                            "status": (
                                "approved"
                                if shots
                                and videos_ready == len(shots)
                                and shots_approved == len(shots)
                                else "pending"
                            ),
                            "label": (
                                f"{videos_ready}/{len(shots)} 视频 · "
                                f"{shots_approved}/{len(shots)} 已审核"
                            ),
                            "approved": bool(
                                shots
                                and videos_ready == len(shots)
                                and shots_approved == len(shots)
                            ),
                        },
                    },
                    "latestRun": (
                        {
                            "id": latest_run.id,
                            "name": latest_run.name,
                            "stage": latest_run.stage,
                            "status": latest_run.status,
                            "updatedAt": latest_run.updated_at,
                        }
                        if latest_run
                        else None
                    ),
                }
            )
            totals["episodes"] += 1
            totals["plansComplete"] += int(plan_complete)
            totals["scenes"] += scene_count
            totals["shots"] += len(shots)
            totals["keyframesReady"] += keyframes_ready
            totals["videosReady"] += videos_ready
            totals["shotsApproved"] += shots_approved
            totals["episodesRendered"] += int(rendered)
            totals["episodesAwaitingApproval"] += int(
                queue_state == "awaiting_approval"
            )
            totals["episodesRunning"] += int(queue_state == "running")
            totals["episodesNeedingRetry"] += int(
                queue_state == "needs_retry"
            )
            totals["episodesReadyToAdvance"] += int(queue_state == "ready")
        return {
            "projectId": project.id,
            "projectTitle": project.title,
            "totals": totals,
            "episodes": episodes,
        }

    def create_project(
        self,
        *,
        idea: str,
        title: str | None,
        project_format: str,
        visual_style: str,
    ) -> dict[str, Any]:
        normalized_idea = idea.strip()
        if not normalized_idea:
            raise ProviderConfigurationError("故事创意不能为空")
        project_id = str(uuid.uuid4())
        resolved_title = (
            (title or "").strip()
            or normalized_idea[:28] + ("…" if len(normalized_idea) > 28 else "")
        )
        workspace = self._workspace_manager.ensure(project_id)
        project = self._repository.create_project(
            project_id=project_id,
            title=resolved_title,
            idea=normalized_idea,
            project_format=project_format,
            visual_style=visual_style,
            workspace_path=str(workspace),
        )
        self._repository.create_document(
            document_id=str(uuid.uuid4()),
            project_id=project.id,
            kind="brief",
            title="项目创作说明",
            content=normalized_idea,
        )
        return _project_view(project)

    def update_stage(
        self,
        project_id: str,
        *,
        active_stage: str,
        status: str | None,
    ) -> dict[str, Any] | None:
        if active_stage not in DRAMA_STAGES:
            raise ProviderConfigurationError("未知的短剧制作阶段")
        project = self._repository.update_project_stage(
            project_id,
            active_stage=active_stage,
            status=status,
        )
        return _project_view(project) if project else None

    def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        latest: dict[str, DramaDocument] = {}
        for document in self._repository.list_documents(project_id):
            latest.setdefault(document.kind, document)
        return [_document_view(document) for document in latest.values()]

    def create_document(
        self,
        project_id: str,
        *,
        kind: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        if kind not in DRAMA_DOCUMENT_KINDS:
            raise ProviderConfigurationError("未知的短剧文档类型")
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        document = self._repository.create_document(
            document_id=str(uuid.uuid4()),
            project_id=project_id,
            kind=kind,
            title=title.strip() or kind,
            content=content,
        )
        self._touch_stages(
            project_id,
            _document_stage(kind),
            reason=f"创建 {kind} 文档版本",
        )
        return _document_view(document)

    def update_document(
        self,
        document_id: str,
        *,
        title: str,
        content: str,
    ) -> dict[str, Any] | None:
        document = self._repository.get_document(document_id)
        if not document:
            return None
        if document.status != "draft":
            raise ProviderConfigurationError("已审批文档不能直接修改，请创建新版本")
        updated = self._repository.update_document(
            document_id,
            title=title.strip() or document.title,
            content=content,
        )
        if updated:
            self._touch_stages(
                updated.project_id,
                _document_stage(updated.kind),
                reason=f"修改 {updated.kind} 草稿",
            )
        return _document_view(updated) if updated else None

    def approve_document(self, document_id: str) -> dict[str, Any] | None:
        current = self._repository.get_document(document_id)
        document = self._repository.approve_document(document_id)
        if current and document:
            self._touch_stages(
                document.project_id,
                _document_stage(document.kind),
                reason=f"审批 {document.kind} 文档",
            )
        return _document_view(document) if document else None

    def production(self, project_id: str) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        result: list[dict[str, Any]] = []
        for episode in self._repository.list_episodes(project_id):
            scenes = []
            for scene in self._repository.list_scenes(episode.id):
                scenes.append(
                    {
                        **_scene_view(scene),
                        "shots": [
                            self._shot_with_candidates(shot)
                            for shot in self._repository.list_shots(scene.id)
                        ],
                    }
                )
            result.append({**_episode_view(episode), "scenes": scenes})
        return result

    def episode_production(self, episode_id: str) -> dict[str, Any]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        scenes = []
        for scene in self._repository.list_scenes(episode.id):
            shots = []
            for shot in self._repository.list_shots(scene.id):
                shots.append(self._shot_with_candidates(shot))
            scenes.append({**_scene_view(scene), "shots": shots})
        shots = [
            shot
            for scene in scenes
            for shot in scene["shots"]
        ]
        return {
            **_episode_view(episode),
            "scenes": scenes,
            "sceneCount": len(scenes),
            "shotCount": len(shots),
            "planComplete": _episode_plan_complete(episode.plan),
        }

    def audit_episode(self, episode_id: str) -> dict[str, Any]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        entities = {
            entity.id: entity
            for entity in self._repository.list_entities(episode.project_id)
        }
        issues: list[dict[str, Any]] = []
        plan = episode.plan
        plan_checks = (
            ("timeScope", plan.time_scope.strip(), "本集尚未定义时间范围"),
            ("locations", plan.locations, "本集尚未定义地点"),
            (
                "interiorExterior",
                plan.interior_exterior,
                "本集尚未区分内外景",
            ),
            ("characters", plan.characters, "本集尚未列出出场人物"),
            ("scenes", plan.scenes, "本集尚未列出场景"),
            ("storyBeats", plan.story_beats, "本集尚未列出故事节拍"),
            (
                "visualRequirements",
                plan.visual_requirements,
                "本集尚未列出画面检查项",
            ),
            (
                "dialogueRequirements",
                plan.dialogue_requirements,
                "本集尚未列出对白检查项",
            ),
        )
        for code, value, message in plan_checks:
            if not value:
                issues.append(
                    _audit_issue(
                        "error",
                        f"episode_plan_{code}",
                        message,
                    )
                )
        if not plan.scene_contracts:
            issues.append(
                _audit_issue(
                    "warning",
                    "episode_scene_contracts_missing",
                    "本集缺少逐场创作契约：目标、障碍、战术、转折、潜台词、"
                    "表演与视觉策略尚未落到结构数据",
                )
            )
        scenes = self._repository.list_scenes(episode.id)
        if not scenes:
            issues.append(
                _audit_issue("error", "episode_scene_missing", "本集没有场次")
            )
        shot_count = 0
        dialogue_shots = 0
        unbound_shots = 0
        direction_missing_count = 0
        scene_plan_mismatch_count = 0
        dialogue_speaker_issue_count = 0
        seen_descriptions: dict[str, str] = {}
        known_speakers = [
            *plan.characters,
            *(entity.name for entity in entities.values()),
        ]
        normalized_known_speakers = [
            normalized
            for name in known_speakers
            if (normalized := _normalized_speaker_name(name))
        ]
        for scene in scenes:
            if not scene.heading.strip():
                issues.append(
                    _audit_issue(
                        "error",
                        "scene_heading_missing",
                        f"场次 {scene.scene_number} 缺少标题",
                    )
                )
            elif not any(
                marker in scene.heading for marker in ("内", "外", "INT", "EXT")
            ):
                issues.append(
                    _audit_issue(
                        "warning",
                        "scene_heading_incomplete",
                        f"场次“{scene.heading}”未明确内景/外景",
                    )
                )
            if not any(
                marker in scene.heading
                for marker in (
                    "日",
                    "夜",
                    "晨",
                    "昏",
                    "白天",
                    "晚上",
                    "清晨",
                    "傍晚",
                    "DAY",
                    "NIGHT",
                )
            ):
                issues.append(
                    _audit_issue(
                        "warning",
                        "scene_time_missing",
                        f"场次“{scene.heading}”未明确日/夜时间",
                    )
                )
            if not scene.summary.strip():
                issues.append(
                    _audit_issue(
                        "warning",
                        "scene_summary_missing",
                        f"场次“{scene.heading}”缺少场景摘要",
                    )
                )
            shots = self._repository.list_shots(scene.id)
            if not shots:
                issues.append(
                    _audit_issue(
                        "error",
                        "scene_shot_missing",
                        f"场次“{scene.heading}”没有镜头",
                    )
                )
            for shot in shots:
                shot_count += 1
                if not shot.description.strip():
                    issues.append(
                        _audit_issue(
                            "error",
                            "shot_description_missing",
                            f"镜头“{shot.title}”缺少画面描述",
                            shot_id=shot.id,
                        )
                    )
                elif len(shot.description.strip()) < 8:
                    issues.append(
                        _audit_issue(
                            "warning",
                            "shot_description_too_short",
                            f"镜头“{shot.title}”画面描述过短，难以指导生成",
                            shot_id=shot.id,
                        )
                    )
                if not any(value.strip() for value in shot.direction.values()):
                    direction_missing_count += 1
                normalized_description = re.sub(
                    r"\s+",
                    "",
                    shot.description,
                )
                if (
                    normalized_description
                    and normalized_description in seen_descriptions
                ):
                    issues.append(
                        _audit_issue(
                            "warning",
                            "shot_description_duplicate",
                            f"镜头“{shot.title}”与"
                            f"“{seen_descriptions[normalized_description]}”"
                            "画面描述重复",
                            shot_id=shot.id,
                        )
                    )
                elif normalized_description:
                    seen_descriptions[normalized_description] = shot.title
                if shot.duration_seconds <= 0:
                    issues.append(
                        _audit_issue(
                            "error",
                            "shot_duration_invalid",
                            f"镜头“{shot.title}”时长无效",
                            shot_id=shot.id,
                        )
                    )
                elif shot.duration_seconds > 15:
                    issues.append(
                        _audit_issue(
                            "warning",
                            "shot_duration_long",
                            f"镜头“{shot.title}”时长超过 15 秒，"
                            "建议拆分以降低生成和连续性风险",
                            shot_id=shot.id,
                        )
                    )
                if shot.dialogue.strip():
                    dialogue_shots += 1
                    speaker = _dialogue_speaker(shot.dialogue)
                    normalized_speaker = _normalized_speaker_name(speaker)
                    if (
                        normalized_speaker
                        and normalized_known_speakers
                        and not any(
                            name in normalized_speaker
                            or normalized_speaker in name
                            for name in normalized_known_speakers
                        )
                    ):
                        dialogue_speaker_issue_count += 1
                        issues.append(
                            _audit_issue(
                                "warning",
                                "shot_dialogue_speaker_unknown",
                                f"镜头“{shot.title}”对白说话人"
                                f"“{speaker}”不在本集人物或资产表中",
                                shot_id=shot.id,
                            )
                        )
                references = self._repository.list_shot_references(shot.id)
                if not references:
                    unbound_shots += 1
                    issues.append(
                        _audit_issue(
                            "warning",
                            "shot_assets_unbound",
                            f"镜头“{shot.title}”没有关联角色、场景或道具",
                            shot_id=shot.id,
                        )
                    )
                for reference in references:
                    entity = entities.get(reference.entity_id)
                    if not entity:
                        issues.append(
                            _audit_issue(
                                "error",
                                "shot_asset_missing",
                                f"镜头“{shot.title}”引用了不存在的资产",
                                shot_id=shot.id,
                                entity_id=reference.entity_id,
                            )
                        )
                    elif entity.status != "locked":
                        issues.append(
                            _audit_issue(
                                "warning",
                                "shot_asset_unlocked",
                                f"镜头“{shot.title}”引用尚未锁定的资产"
                                f"“{entity.name}”",
                                shot_id=shot.id,
                                entity_id=entity.id,
                            )
                        )
        if direction_missing_count:
            issues.append(
                _audit_issue(
                    "warning",
                    "shot_direction_missing",
                    f"{direction_missing_count} 个镜头缺少结构化导演设计："
                    "景别、角度、机位运动、调度、表演、构图、灯光或声音",
                )
            )
        if plan.scenes and len(plan.scenes) != len(scenes):
            scene_plan_mismatch_count += 1
            issues.append(
                _audit_issue(
                    "warning",
                    "episode_plan_scene_count_mismatch",
                    f"分集计划列出 {len(plan.scenes)} 个场景，"
                    f"实际拆解为 {len(scenes)} 个场次",
                )
            )
        contract_numbers = [
            contract.scene_number for contract in plan.scene_contracts
        ]
        duplicate_contracts = sorted(
            {
                number
                for number in contract_numbers
                if contract_numbers.count(number) > 1
            }
        )
        if duplicate_contracts:
            issues.append(
                _audit_issue(
                    "warning",
                    "episode_scene_contract_duplicate",
                    "场景契约编号重复："
                    f"{'、'.join(map(str, duplicate_contracts))}",
                )
            )
        actual_scene_numbers = {scene.scene_number for scene in scenes}
        orphan_contracts = sorted(
            set(contract_numbers) - actual_scene_numbers
        )
        if orphan_contracts and actual_scene_numbers:
            issues.append(
                _audit_issue(
                    "warning",
                    "episode_scene_contract_orphaned",
                    "场景契约引用了不存在的场次编号："
                    f"{'、'.join(map(str, orphan_contracts))}",
                )
            )
        if plan.locations and scenes:
            normalized_headings = [
                re.sub(r"\s+", "", scene.heading) for scene in scenes
            ]
            missing_locations = [
                location
                for location in plan.locations
                if not any(
                    re.sub(r"\s+", "", location) in heading
                    or heading in re.sub(r"\s+", "", location)
                    for heading in normalized_headings
                )
            ]
            if missing_locations:
                scene_plan_mismatch_count += len(missing_locations)
                issues.append(
                    _audit_issue(
                        "warning",
                        "episode_plan_location_not_found",
                        "计划地点未出现在场次标题中："
                        + "、".join(missing_locations),
                    )
                )
        error_count = sum(issue["severity"] == "error" for issue in issues)
        warning_count = sum(
            issue["severity"] == "warning" for issue in issues
        )
        return {
            "episodeId": episode.id,
            "episodeNumber": episode.episode_number,
            "title": episode.title,
            "score": max(0, 100 - error_count * 15 - warning_count * 5),
            "readyForAssets": error_count == 0,
            "readyForVideo": error_count == 0 and unbound_shots == 0,
            "sceneCount": len(scenes),
            "shotCount": shot_count,
            "dialogueShotCount": dialogue_shots,
            "unboundShotCount": unbound_shots,
            "scenePlanMismatchCount": scene_plan_mismatch_count,
            "dialogueSpeakerIssueCount": dialogue_speaker_issue_count,
            "errorCount": error_count,
            "warningCount": warning_count,
            "issues": issues,
        }

    def audit_script(self, project_id: str) -> dict[str, Any]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        script = next(
            (
                document
                for document in self._repository.list_documents(project_id)
                if document.kind == "script"
            ),
            None,
        )
        issues: list[dict[str, Any]] = []
        if not script:
            issues.append(
                _audit_issue("error", "script_missing", "项目还没有剧本")
            )
            content = ""
        else:
            content = script.content
            if not content.strip():
                issues.append(
                    _audit_issue(
                        "error",
                        "script_empty",
                        "剧本正文为空",
                    )
                )
        episode_markers = list(
            re.finditer(r"(?m)^(?:#{1,4}\s*)?第\s*(\d+)\s*集", content)
        )
        scene_markers = list(
            re.finditer(
                r"(?m)^\s*(?:#{1,4}\s*)?(?:场|场景)\s*(\d+(?:-\d+)?)",
                content,
            )
        )
        placeholder_lines = [
            line.strip()
            for line in content.splitlines()
            if re.search(r"待填写|待定|TODO|TBD", line, re.IGNORECASE)
        ]
        dialogue_lines = [
            line.strip()
            for line in content.splitlines()
            if re.match(r"^[^：:\n]{1,30}[：:]", line.strip())
        ]
        episode_numbers = [int(match.group(1)) for match in episode_markers]
        if content.strip() and not episode_markers:
            issues.append(
                _audit_issue(
                    "error",
                    "script_episode_missing",
                    "剧本没有识别到“第 N 集”分集标题",
                )
            )
        duplicates = sorted({
            number
            for number in episode_numbers
            if episode_numbers.count(number) > 1
        })
        if duplicates:
            issues.append(
                _audit_issue(
                    "error",
                    "script_episode_duplicate",
                    f"重复的分集编号：{'、'.join(map(str, duplicates))}",
                )
            )
        if content.strip() and not scene_markers:
            issues.append(
                _audit_issue(
                    "error",
                    "script_scene_missing",
                    "剧本没有识别到“场 N”场次标题",
                )
            )
        if content.strip() and not dialogue_lines:
            issues.append(
                _audit_issue(
                    "warning",
                    "script_dialogue_missing",
                    "剧本没有识别到“角色：对白”格式的对白",
                )
            )
        craft = _script_craft_analysis(content)
        for craft_issue in craft["issues"]:
            issues.append(
                _audit_issue(
                    "warning",
                    str(craft_issue["code"]),
                    str(craft_issue["message"]),
                    scene_number=craft_issue.get("sceneNumber"),
                )
            )
        for line in placeholder_lines[:20]:
            issues.append(
                _audit_issue(
                    "warning",
                    "script_placeholder",
                    f"仍存在占位内容：{line[:100]}",
                )
            )
        error_count = sum(issue["severity"] == "error" for issue in issues)
        warning_count = sum(
            issue["severity"] == "warning" for issue in issues
        )
        return {
            "projectId": project_id,
            "documentId": script.id if script else None,
            "documentVersion": script.version if script else None,
            "documentStatus": script.status if script else None,
            "score": max(0, 100 - error_count * 15 - warning_count * 5),
            "readyForReview": error_count == 0 and warning_count == 0,
            "episodeCount": len(set(episode_numbers)),
            "sceneCount": len(scene_markers),
            "dialogueLineCount": len(dialogue_lines),
            "placeholderCount": len(placeholder_lines),
            "craftSummary": craft["summary"],
            "sceneCraft": craft["scenes"],
            "errorCount": error_count,
            "warningCount": warning_count,
            "issues": issues,
        }

    def audit(self, project_id: str) -> dict[str, Any]:
        project = self._repository.get_project(project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        entities = {
            entity.id: entity
            for entity in self._repository.list_entities(project_id)
        }
        issues: list[dict[str, Any]] = []
        episodes = self._repository.list_episodes(project_id)
        if not episodes:
            issues.append(
                _audit_issue(
                    "error",
                    "missing_episode",
                    "项目还没有分集",
                )
            )
        for entity in entities.values():
            if entity.status != "locked":
                issues.append(
                    _audit_issue(
                        "warning",
                        "entity_not_locked",
                        f"资产“{entity.name}”尚未锁定",
                        entity_id=entity.id,
                    )
                )
            if entity.kind == "character" and not entity.voice_name:
                issues.append(
                    _audit_issue(
                        "warning",
                        "character_voice_missing",
                        f"角色“{entity.name}”尚未配置音色",
                        entity_id=entity.id,
                    )
                )
            required_slots = _required_asset_slots(entity.kind)
            missing_slots = [
                label
                for slot, label in required_slots
                if not entity.asset_slots.get(slot)
            ]
            if missing_slots and entity.status == "locked":
                issues.append(
                    _audit_issue(
                        "warning",
                        "asset_slots_incomplete",
                        f"资产“{entity.name}”缺少专业槽位："
                        f"{'、'.join(missing_slots)}",
                        entity_id=entity.id,
                    )
                )
        reviews = self._repository.list_reviews(project_id)
        latest_role_reviews: dict[tuple[str, str], DramaReview] = {}
        for review in reviews:
            if review.role_id in DRAMA_STAGE_OWNERS.get(review.stage, ()):
                latest_role_reviews[(review.stage, review.role_id)] = review
        for review in latest_role_reviews.values():
            if review.status in {"failed", "changes_requested"}:
                issues.append(
                    _audit_issue(
                        "warning",
                        "stage_review_open",
                        f"{review.stage} 阶段仍有"
                        f"{'未通过' if review.status == 'failed' else '待修改'}"
                        "的角色审核",
                    )
                )
        shot_count = 0
        for episode in episodes:
            cues = (
                list(episode.subtitle_cues)
                if episode.subtitle_cues
                else self._default_subtitles(episode.id)
            )
            has_dialogue = False
            if not _episode_plan_complete(episode.plan):
                issues.append(
                    _audit_issue(
                        "warning",
                        "episode_plan_incomplete",
                        f"分集“{episode.title}”的时间和场景拆解不完整",
                    )
                )
            for scene in self._repository.list_scenes(episode.id):
                for shot in self._repository.list_shots(scene.id):
                    shot_count += 1
                    if not shot.video_asset_id:
                        issues.append(
                            _audit_issue(
                                "error",
                                "shot_video_missing",
                                f"镜头“{shot.title}”缺少视频",
                                shot_id=shot.id,
                            )
                        )
                    if not shot.grid9_asset_id:
                        issues.append(
                            _audit_issue(
                                "info",
                                "shot_grid9_missing",
                                f"镜头“{shot.title}”尚未绑定九宫格连续帧",
                                shot_id=shot.id,
                            )
                        )
                    if not shot.storyboard_asset_id:
                        issues.append(
                            _audit_issue(
                                "info",
                                "shot_storyboard_missing",
                                f"镜头“{shot.title}”尚未绑定故事板",
                                shot_id=shot.id,
                            )
                        )
                    if not shot.audio_asset_id and shot.dialogue:
                        issues.append(
                            _audit_issue(
                                "warning",
                                "shot_audio_missing",
                                f"镜头“{shot.title}”有对白但缺少音频",
                                shot_id=shot.id,
                            )
                        )
                    if shot.dialogue:
                        has_dialogue = True
                    references = self._repository.list_shot_references(shot.id)
                    if not references:
                        issues.append(
                            _audit_issue(
                                "warning",
                                "shot_entities_missing",
                                f"镜头“{shot.title}”没有关联角色或场景资产",
                                shot_id=shot.id,
                            )
                        )
                    for reference in references:
                        entity = entities.get(reference.entity_id)
                        if not entity:
                            issues.append(
                                _audit_issue(
                                    "error",
                                    "shot_entity_missing",
                                    f"镜头“{shot.title}”引用了不存在的资产",
                                    shot_id=shot.id,
                                    entity_id=reference.entity_id,
                                )
                            )
                        elif entity.status != "locked":
                            issues.append(
                                _audit_issue(
                                    "warning",
                                    "shot_entity_unlocked",
                                    f"镜头“{shot.title}”引用了未锁定资产“{entity.name}”",
                                    shot_id=shot.id,
                                    entity_id=entity.id,
                                )
                            )
            if has_dialogue and not cues:
                issues.append(
                    _audit_issue(
                        "warning",
                        "subtitle_missing",
                        f"分集“{episode.title}”有对白但没有字幕",
                    )
                )
            if episode.status != "rendered":
                issues.append(
                    _audit_issue(
                        "info",
                        "episode_not_rendered",
                        f"分集“{episode.title}”尚未渲染",
                    )
                )
        error_count = sum(issue["severity"] == "error" for issue in issues)
        warning_count = sum(
            issue["severity"] == "warning" for issue in issues
        )
        score = max(0, 100 - error_count * 20 - warning_count * 5)
        return {
            "projectId": project_id,
            "score": score,
            "ready": error_count == 0,
            "entityCount": len(entities),
            "shotCount": shot_count,
            "errorCount": error_count,
            "warningCount": warning_count,
            "issues": issues,
        }

    def create_episode(
        self,
        project_id: str,
        *,
        title: str,
        synopsis: str,
        plan: DramaEpisodePlan | None = None,
    ) -> dict[str, Any]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        episode = self._repository.create_episode(
            episode_id=str(uuid.uuid4()),
            project_id=project_id,
            title=title.strip() or "未命名分集",
            synopsis=synopsis,
            plan=plan,
        )
        self._touch_stages(
            project_id,
            "breakdown",
            "keyframes",
            "clips",
            "timeline",
            reason=f"新增第 {episode.episode_number} 集",
        )
        return _episode_view(episode)

    def update_episode_plan(
        self,
        episode_id: str,
        plan: DramaEpisodePlan,
    ) -> dict[str, Any]:
        episode = self._repository.update_episode_plan(
            episode_id,
            plan=plan,
        )
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        self._touch_stages(
            episode.project_id,
            "breakdown",
            reason=f"更新第 {episode.episode_number} 集计划",
        )
        return _episode_view(episode)

    def subtitles(self, episode_id: str) -> list[dict[str, Any]]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        cues = (
            list(episode.subtitle_cues)
            if episode.subtitle_cues
            else self._default_subtitles(episode_id)
        )
        return [_subtitle_view(cue) for cue in cues]

    def update_subtitles(
        self,
        episode_id: str,
        cues: list[dict[str, object]],
    ) -> list[dict[str, Any]]:
        if not self._repository.get_episode(episode_id):
            raise ProviderConfigurationError("短剧分集不存在")
        normalized = _normalize_subtitles(cues)
        updated = self._repository.update_episode_subtitles(
            episode_id,
            cues=normalized,
        )
        if not updated:
            raise ProviderConfigurationError("短剧分集不存在")
        self._touch_stages(
            updated.project_id,
            "timeline",
            reason="修改字幕",
        )
        return [_subtitle_view(cue) for cue in updated.subtitle_cues]

    def update_audio_mix(
        self,
        episode_id: str,
        *,
        music_asset_id: str | None,
        music_volume_db: float,
        ambience_asset_id: str | None,
        ambience_volume_db: float,
        ducking: bool,
        sound_effects: list[dict[str, object]],
    ) -> dict[str, Any]:
        if not self._repository.get_episode(episode_id):
            raise ProviderConfigurationError("短剧分集不存在")
        if not -60 <= music_volume_db <= 12:
            raise ProviderConfigurationError("音乐音量必须在 -60–12 dB 之间")
        if not -60 <= ambience_volume_db <= 12:
            raise ProviderConfigurationError("环境声音量必须在 -60–12 dB 之间")
        normalized_effects: list[DramaSoundEffect] = []
        for index, effect in enumerate(sound_effects):
            asset_id = str(effect.get("assetId") or "")
            start = float(effect.get("startSeconds") or 0)
            duration = float(effect.get("durationSeconds") or 0)
            volume = float(effect.get("volumeDb") or 0)
            if not asset_id:
                raise ProviderConfigurationError(
                    f"第 {index + 1} 个音效缺少素材"
                )
            if start < 0 or duration <= 0:
                raise ProviderConfigurationError(
                    f"第 {index + 1} 个音效时间范围无效"
                )
            if not -60 <= volume <= 12:
                raise ProviderConfigurationError(
                    f"第 {index + 1} 个音效音量必须在 -60–12 dB 之间"
                )
            normalized_effects.append(
                DramaSoundEffect(
                    asset_id=asset_id,
                    start_seconds=start,
                    duration_seconds=duration,
                    volume_db=volume,
                )
            )
        updated = self._repository.update_episode_audio_mix(
            episode_id,
            audio_mix=DramaAudioMix(
                music_asset_id=music_asset_id or None,
                music_volume_db=music_volume_db,
                ambience_asset_id=ambience_asset_id or None,
                ambience_volume_db=ambience_volume_db,
                ducking=ducking,
                sound_effects=tuple(normalized_effects),
            ),
        )
        if not updated:
            raise ProviderConfigurationError("短剧分集不存在")
        self._touch_stages(
            updated.project_id,
            "timeline",
            reason="修改整集音频混音",
        )
        return _audio_mix_view(updated.audio_mix)

    def update_subtitle_style(
        self,
        episode_id: str,
        *,
        preset: str,
        font_size: int,
        outline: float,
        margin_v: int,
        primary_color: str,
        outline_color: str,
    ) -> dict[str, Any]:
        if not self._repository.get_episode(episode_id):
            raise ProviderConfigurationError("短剧分集不存在")
        if preset not in {"short_video", "cinema", "minimal", "custom"}:
            raise ProviderConfigurationError("未知的字幕样式")
        if not 12 <= font_size <= 80:
            raise ProviderConfigurationError("字幕字号必须在 12–80 之间")
        if not 0 <= outline <= 8:
            raise ProviderConfigurationError("字幕描边必须在 0–8 之间")
        if not 0 <= margin_v <= 600:
            raise ProviderConfigurationError("字幕下边距必须在 0–600 之间")
        for color in (primary_color, outline_color):
            if not color.startswith("#") or len(color) != 7:
                raise ProviderConfigurationError("字幕颜色格式必须为 #RRGGBB")
        updated = self._repository.update_episode_subtitle_style(
            episode_id,
            subtitle_style=DramaSubtitleStyle(
                preset=preset,
                font_size=font_size,
                outline=outline,
                margin_v=margin_v,
                primary_color=primary_color.upper(),
                outline_color=outline_color.upper(),
            ),
        )
        if not updated:
            raise ProviderConfigurationError("短剧分集不存在")
        self._touch_stages(
            updated.project_id,
            "timeline",
            reason="修改字幕样式",
        )
        return _subtitle_style_view(updated.subtitle_style)

    async def render_episode(
        self,
        episode_id: str,
        *,
        transition: str = "none",
        transition_duration: float = 0.4,
        strict_approvals: bool = True,
    ) -> dict[str, Any]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        project = self._repository.get_project(episode.project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        if transition not in {"none", "crossfade"}:
            raise ProviderConfigurationError("未知的镜头转场类型")
        if transition_duration < 0.1 or transition_duration > 3:
            raise ProviderConfigurationError("转场时长必须在 0.1–3 秒之间")
        shots = [
            shot
            for scene in self._repository.list_scenes(episode.id)
            for shot in self._repository.list_shots(scene.id)
        ]
        if not shots:
            raise ProviderConfigurationError("本集还没有镜头")
        missing = [shot.title for shot in shots if not shot.video_asset_id]
        if missing:
            raise ProviderConfigurationError(
                f"以下镜头缺少视频，无法合成整集：{'、'.join(missing)}"
            )
        if strict_approvals:
            unapproved = [
                shot.title for shot in shots if shot.status != "approved"
            ]
            if unapproved:
                raise ProviderConfigurationError(
                    "以下镜头尚未通过审核，不能合成最终成片："
                    + "、".join(unapproved)
                )
        subtitle_cues = (
            list(episode.subtitle_cues)
            if episode.subtitle_cues
            else self._default_subtitles(episode.id)
        )
        if not episode.subtitle_cues and subtitle_cues:
            self._repository.update_episode_subtitles(
                episode.id,
                cues=subtitle_cues,
            )
        manifest_id = str(uuid.uuid4())
        manifest_data = self._build_export_manifest(
            project,
            episode,
            shots=shots,
            subtitle_cues=subtitle_cues,
            transition=transition,
            transition_duration=transition_duration,
        )
        export_asset_id = await asyncio.to_thread(
            self._timeline_renderer.render_timeline,
            [str(shot.video_asset_id) for shot in shots],
            aspect_ratio=project.format,
            filename=f"episode-{episode.episode_number:02d}.mp4",
            subtitle_cues=[
                _subtitle_view(cue) for cue in subtitle_cues
            ],
            audio_asset_ids=[shot.audio_asset_id for shot in shots],
            subtitle_style=_subtitle_style_view(episode.subtitle_style),
            transition=transition,
            transition_duration=transition_duration,
            music_asset_id=episode.audio_mix.music_asset_id,
            music_volume_db=episode.audio_mix.music_volume_db,
            ambience_asset_id=episode.audio_mix.ambience_asset_id,
            ambience_volume_db=episode.audio_mix.ambience_volume_db,
            ducking=episode.audio_mix.ducking,
            sound_effects=[
                {
                    "assetId": effect.asset_id,
                    "startSeconds": effect.start_seconds,
                    "durationSeconds": effect.duration_seconds,
                    "volumeDb": effect.volume_db,
                }
                for effect in episode.audio_mix.sound_effects
            ],
        )
        self._repository.create_export_manifest(
            manifest_id=manifest_id,
            project_id=project.id,
            episode_id=episode.id,
            export_asset_id=export_asset_id,
            manifest=manifest_data,
        )
        updated = self._repository.update_episode_export(
            episode_id,
            export_asset_id=export_asset_id,
            export_manifest_id=manifest_id,
        )
        return {
            **_episode_view(updated),
            "exportAssetUrl": f"/api/assets/{export_asset_id}",
            "exportManifest": manifest_data,
        }

    def export_manifests(self, episode_id: str) -> list[dict[str, Any]]:
        if not self._repository.get_episode(episode_id):
            raise ProviderConfigurationError("短剧分集不存在")
        return [
            {
                "id": manifest.id,
                "projectId": manifest.project_id,
                "episodeId": manifest.episode_id,
                "exportAssetId": manifest.export_asset_id,
                "createdAt": manifest.created_at,
                "manifest": manifest.manifest,
            }
            for manifest in self._repository.list_export_manifests(episode_id)
        ]

    def _build_export_manifest(
        self,
        project,
        episode,
        *,
        shots,
        subtitle_cues: list[DramaSubtitleCue],
        transition: str,
        transition_duration: float,
    ) -> dict[str, Any]:
        gates = {
            gate["stage"]: gate
            for gate in self.production_control(project.id)["gates"]
        }
        required_stages = (
            "script",
            "breakdown",
            "assets",
            "keyframes",
            "clips",
            "timeline",
        )
        approval_warnings = [
            {
                "stage": stage,
                "label": gates[stage]["label"],
                "revision": gates[stage]["revision"],
                "approvedRevision": gates[stage]["approvedRevision"],
                "stale": gates[stage]["stale"],
            }
            for stage in required_stages
            if not gates[stage]["approved"]
        ]
        scenes = []
        for scene in self._repository.list_scenes(episode.id):
            scenes.append(
                {
                    **_scene_view(scene),
                    "shots": [
                        {
                            **_shot_view(shot),
                            "entityReferences": [
                                {
                                    "entityId": reference.entity_id,
                                    "role": reference.role,
                                }
                                for reference in self._repository.list_shot_references(
                                    shot.id
                                )
                            ],
                        }
                        for shot in self._repository.list_shots(scene.id)
                    ],
                }
            )
        return {
            "schemaVersion": 1,
            "renderedAt": _utc_timestamp(),
            "project": _project_view(project),
            "episode": {
                **_episode_view(episode),
                "scenes": scenes,
            },
            "documents": [
                _document_view(document)
                for document in self._repository.list_documents(project.id)
            ],
            "entities": [
                _entity_view(entity)
                for entity in self._repository.list_entities(project.id)
            ],
            "stageGates": [
                gates[stage] for stage in required_stages
            ],
            "approvalComplete": not approval_warnings,
            "approvalWarnings": approval_warnings,
            "rendering": {
                "transition": transition,
                "transitionDuration": transition_duration,
                "subtitleCues": [
                    _subtitle_view(cue) for cue in subtitle_cues
                ],
                "subtitleStyle": _subtitle_style_view(
                    episode.subtitle_style
                ),
                "audioMix": _audio_mix_view(episode.audio_mix),
                "shotOrder": [shot.id for shot in shots],
            },
        }

    def _default_subtitles(self, episode_id: str) -> list[DramaSubtitleCue]:
        shots = [
            shot
            for scene in self._repository.list_scenes(episode_id)
            for shot in self._repository.list_shots(scene.id)
        ]
        cues: list[DramaSubtitleCue] = []
        cursor = 0.0
        for shot in shots:
            duration = max(0.1, shot.duration_seconds)
            text = shot.dialogue.strip()
            if text:
                cues.append(
                    DramaSubtitleCue(
                        start_seconds=cursor,
                        end_seconds=cursor + duration,
                        text=text,
                    )
                )
            cursor += duration
        return cues

    def create_scene(
        self,
        episode_id: str,
        *,
        heading: str,
        summary: str,
        script_document_id: str | None,
    ) -> dict[str, Any]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        scene = self._repository.create_scene(
            scene_id=str(uuid.uuid4()),
            episode_id=episode_id,
            heading=heading.strip() or "未命名场次",
            summary=summary,
            script_document_id=script_document_id,
        )
        self._touch_stages(
            episode.project_id,
            "breakdown",
            "keyframes",
            "clips",
            reason=f"新增第 {episode.episode_number} 集场次",
        )
        return _scene_view(scene)

    def create_shot(
        self,
        scene_id: str,
        *,
        title: str,
        description: str,
        dialogue: str,
        duration_seconds: float,
        direction: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        scene = self._repository.get_scene(scene_id)
        if not scene:
            raise ProviderConfigurationError("短剧场次不存在")
        shot = self._repository.create_shot(
            shot_id=str(uuid.uuid4()),
            scene_id=scene_id,
            title=title.strip() or "未命名镜头",
            description=description,
            dialogue=dialogue,
            duration_seconds=max(0.1, duration_seconds),
            direction=_string_mapping(direction),
        )
        episode = self._repository.get_episode(scene.episode_id)
        if episode:
            self._touch_stages(
                episode.project_id,
                "breakdown",
                "keyframes",
                "clips",
                reason=f"新增第 {episode.episode_number} 集镜头",
            )
        return _shot_view(shot)

    def update_shot_status(
        self,
        shot_id: str,
        *,
        status: str,
        reviewer: str = "user",
        note: str = "",
    ) -> dict[str, Any] | None:
        return self.update_shot(
            shot_id,
            status=status,
            status_reviewer=reviewer,
            status_note=note,
        )

    def update_shot_prompt(
        self,
        shot_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> dict[str, Any] | None:
        allowed_slots = {
            "first_frame",
            "last_frame",
            "grid9",
            "storyboard",
            "video",
            "audio",
        }
        if slot not in allowed_slots:
            raise ProviderConfigurationError("未知的镜头提示词槽位")
        if len(prompt) > 12000:
            raise ProviderConfigurationError("镜头提示词不能超过 12000 字符")
        shot = self._repository.get_shot(shot_id)
        if not shot:
            return None
        updated = self._repository.update_shot_prompt(
            shot_id,
            slot=slot,
            prompt=prompt,
        )
        if not updated:
            return None
        scene = self._repository.get_scene(updated.scene_id)
        episode = (
            self._repository.get_episode(scene.episode_id) if scene else None
        )
        if episode:
            stages = (
                ("keyframes", "clips", "timeline")
                if slot in {
                    "first_frame",
                    "last_frame",
                    "grid9",
                    "storyboard",
                }
                else ("clips", "timeline")
            )
            self._touch_stages(
                episode.project_id,
                *stages,
                reason=f"修改镜头 {updated.shot_number} 的 {slot} 提示词",
            )
        return self._shot_with_candidates(updated)

    def update_shot_direction(
        self,
        shot_id: str,
        *,
        direction: dict[str, str],
    ) -> dict[str, Any] | None:
        return self.update_shot(
            shot_id,
            direction=direction,
            status_reviewer="system",
            status_note="更新结构化镜头导演设计，原审核状态失效",
        )

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
        status_reviewer: str = "system",
        status_note: str = "",
    ) -> dict[str, Any] | None:
        if status is not None and status not in {
            "planned",
            "keyframe_ready",
            "clip_ready",
            "approved",
        }:
            raise ProviderConfigurationError("未知的镜头状态")
        current = self._repository.get_shot(shot_id)
        if not current:
            return None
        if (
            status == "approved"
            and not (video_asset_id or current.video_asset_id)
        ):
            raise ProviderConfigurationError("镜头没有视频时不能标记为已通过")
        if status is None:
            if video_asset_id:
                status = "clip_ready"
            elif current.status == "approved" and (
                direction is not None
                or audio_asset_id
                or any(
                    asset_id
                    for asset_id in (
                        first_frame_asset_id,
                        last_frame_asset_id,
                        grid9_asset_id,
                        storyboard_asset_id,
                    )
                )
            ):
                status = (
                    "clip_ready"
                    if current.video_asset_id
                    else "keyframe_ready"
                )
        shot = self._repository.update_shot(
            shot_id,
            status=status,
            first_frame_asset_id=first_frame_asset_id,
            last_frame_asset_id=last_frame_asset_id,
            grid9_asset_id=grid9_asset_id,
            storyboard_asset_id=storyboard_asset_id,
            video_asset_id=video_asset_id,
            audio_asset_id=audio_asset_id,
            direction=(
                _string_mapping(direction)
                if direction is not None
                else None
            ),
        )
        if not shot:
            return None
        if shot.status != current.status:
            self._record_shot_status_event(
                shot.id,
                from_status=current.status,
                to_status=shot.status,
                reviewer=status_reviewer,
                note=status_note,
            )
        for slot, asset_id in (
            ("first_frame", first_frame_asset_id),
            ("last_frame", last_frame_asset_id),
            ("grid9", grid9_asset_id),
            ("storyboard", storyboard_asset_id),
            ("video", video_asset_id),
            ("audio", audio_asset_id),
        ):
            if asset_id:
                self._record_shot_candidate(shot, slot, asset_id)
        if direction is not None or any(
            asset_id
            for asset_id in (
                first_frame_asset_id,
                last_frame_asset_id,
                grid9_asset_id,
                storyboard_asset_id,
                video_asset_id,
                audio_asset_id,
            )
        ):
            scene = self._repository.get_scene(shot.scene_id)
            episode = (
                self._repository.get_episode(scene.episode_id)
                if scene
                else None
            )
            if episode:
                self._touch_stages(
                    episode.project_id,
                    "breakdown",
                    "keyframes",
                    "clips",
                    "timeline",
                    reason=f"修改第 {episode.episode_number} 集镜头素材",
                )
        return self._shot_with_candidates(shot)

    def list_entities(self, project_id: str) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        return [
            self._entity_with_candidates(entity)
            for entity in self._repository.list_entities(project_id)
        ]

    def create_entity(
        self,
        project_id: str,
        *,
        kind: str,
        name: str,
        description: str,
        profile: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        if kind not in DRAMA_ENTITY_KINDS:
            raise ProviderConfigurationError("未知的短剧实体类型")
        if not name.strip():
            raise ProviderConfigurationError("实体名称不能为空")
        entity = self._repository.create_entity(
            entity_id=str(uuid.uuid4()),
            project_id=project_id,
            kind=kind,
            name=name.strip(),
            description=description,
            profile=_string_mapping(profile),
        )
        self._touch_stages(
            project_id,
            "assets",
            "keyframes",
            "clips",
            "timeline",
            reason=f"新增实体资产“{entity.name}”",
        )
        return _entity_view(entity)

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
    ) -> dict[str, Any] | None:
        entity = self._repository.get_entity(entity_id)
        if not entity:
            return None
        if status not in {"draft", "locked"}:
            raise ProviderConfigurationError("未知的实体状态")
        if status == "locked" and not primary_asset_id:
            raise ProviderConfigurationError("锁定实体前必须先绑定主素材")
        if not -10 <= voice_rate <= 10:
            raise ProviderConfigurationError("角色语速必须在 -10–10 之间")
        updated = self._repository.update_entity(
            entity_id,
            name=name.strip() or entity.name,
            description=description,
            status=status,
            primary_asset_id=primary_asset_id,
            reference_asset_ids=[
                value for value in reference_asset_ids if value
            ],
            asset_slots={
                key.strip(): value
                for key, value in (asset_slots or {}).items()
                if key.strip() and value
            },
            profile=(
                entity.profile
                if profile is None
                else _string_mapping(profile)
            ),
            voice_name=voice_name or None,
            voice_rate=voice_rate,
        )
        if not updated:
            return None
        self._record_entity_candidates(
            updated,
            primary_asset_id=primary_asset_id,
            reference_asset_ids=reference_asset_ids,
            asset_slots=asset_slots or {},
        )
        self._touch_stages(
            updated.project_id,
            "assets",
            "keyframes",
            "clips",
            "timeline",
            reason=f"修改实体资产“{updated.name}”",
        )
        return self._entity_with_candidates(updated)

    def update_entity_prompt(
        self,
        entity_id: str,
        *,
        slot: str,
        prompt: str,
    ) -> dict[str, Any] | None:
        if not slot.strip():
            raise ProviderConfigurationError("资产提示词槽位不能为空")
        if len(prompt) > 12000:
            raise ProviderConfigurationError("资产提示词不能超过 12000 字符")
        entity = self._repository.get_entity(entity_id)
        if not entity:
            return None
        updated = self._repository.update_entity_prompt(
            entity_id,
            slot=slot.strip(),
            prompt=prompt,
        )
        if not updated:
            return None
        self._touch_stages(
            updated.project_id,
            "assets",
            "keyframes",
            "clips",
            "timeline",
            reason=f"修改资产“{updated.name}”的 {slot} 提示词",
        )
        return self._entity_with_candidates(updated)

    def set_shot_references(
        self,
        shot_id: str,
        references: list[dict[str, str]],
    ) -> list[dict[str, str]] | None:
        shot = self._repository.get_shot(shot_id)
        if not shot:
            return None
        scene = self._repository.get_scene(shot.scene_id)
        episode = scene and self._repository.get_episode(scene.episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧镜头缺少有效场次")
        normalized: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for reference in references:
            entity_id = str(reference.get("entityId") or "")
            role = str(reference.get("role") or "reference")
            entity = (
                self._repository.get_entity(entity_id) if entity_id else None
            )
            if not entity:
                raise ProviderConfigurationError("镜头引用的短剧实体不存在")
            if entity.project_id != episode.project_id:
                raise ProviderConfigurationError("镜头不能引用其他项目的短剧实体")
            key = (entity_id, role)
            if key in seen:
                continue
            seen.add(key)
            normalized.append((entity_id, role))
        saved = self._repository.replace_shot_references(
            shot_id,
            normalized,
        )
        self._touch_stages(
            episode.project_id,
            "keyframes",
            "clips",
            "timeline",
            reason=f"修改镜头 {shot.shot_number} 的资产引用",
        )
        return [
            {"entityId": item.entity_id, "role": item.role}
            for item in saved
        ]

    def get_shot_references(
        self,
        shot_id: str,
    ) -> list[dict[str, str]] | None:
        if not self._repository.get_shot(shot_id):
            return None
        return [
            {"entityId": item.entity_id, "role": item.role}
            for item in self._repository.list_shot_references(shot_id)
        ]

    def shot_status_history(
        self,
        shot_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]] | None:
        if not self._repository.get_shot(shot_id):
            return None
        return [
            _shot_status_event_view(event)
            for event in self._repository.list_shot_status_events(
                shot_id,
                limit=limit,
            )
        ]

    def list_asset_candidates(
        self,
        project_id: str,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        slot: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        if (
            subject_type is not None
            and subject_type not in DRAMA_CANDIDATE_SUBJECT_TYPES
        ):
            raise ProviderConfigurationError("未知的候选素材主体类型")
        return [
            _asset_candidate_view(candidate)
            for candidate in self._repository.list_asset_candidates(
                project_id,
                subject_type=subject_type,
                subject_id=subject_id,
                slot=slot,
            )
        ]

    def update_asset_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
    ) -> dict[str, Any]:
        if status not in DRAMA_CANDIDATE_STATUSES:
            raise ProviderConfigurationError("未知的候选素材状态")
        candidate = self._repository.get_asset_candidate(candidate_id)
        if not candidate:
            raise ProviderConfigurationError("候选素材不存在")
        if status == "rejected" and candidate.status == "selected":
            raise ProviderConfigurationError(
                "当前主素材不能直接弃用，请先选择其他候选"
            )
        if status == "selected":
            if candidate.subject_type == "shot":
                self.bind_shot_asset(
                    candidate.subject_id,
                    slot=candidate.slot,
                    asset_id=candidate.asset_id,
                )
            else:
                self.bind_entity_asset(
                    candidate.subject_id,
                    slot=candidate.slot,
                    asset_id=candidate.asset_id,
                )
        updated = self._repository.update_asset_candidate_status(
            candidate_id,
            status=status,
        )
        if not updated:
            raise ProviderConfigurationError("候选素材不存在")
        return _asset_candidate_view(updated)

    def list_production_runs(
        self,
        project_id: str,
        *,
        episode_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        return [
            self._production_run_view(run)
            for run in self._repository.list_production_runs(
                project_id,
                episode_id=episode_id,
                limit=limit,
            )
        ]

    def get_production_run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_production_run(run_id)
        if not run:
            raise ProviderConfigurationError("短剧制作运行不存在")
        return self._production_run_view(run)

    def create_production_run(
        self,
        project_id: str,
        *,
        episode_id: str,
        stage: str,
        name: str,
        requires_approval: bool,
        max_parallel: int,
        items: list[dict[str, Any]],
        planning: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        project = self._repository.get_project(project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        episode = self._repository.get_episode(episode_id)
        if not episode or episode.project_id != project.id:
            raise ProviderConfigurationError("短剧分集不属于当前项目")
        if stage not in {"assets", "keyframes", "clips"}:
            raise ProviderConfigurationError("制作运行目前仅支持资产、分镜和镜头视频阶段")
        if not items:
            raise ProviderConfigurationError("制作运行至少需要一个任务")
        if len(items) > 100:
            raise ProviderConfigurationError("单次制作运行最多包含 100 个任务")
        if not 1 <= max_parallel <= 4:
            raise ProviderConfigurationError("并行数必须在 1–4 之间")
        self._require_episode_ready_for_production(
            episode_id,
            stage=stage,
        )
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for position, item in enumerate(items):
            target_type = str(item.get("targetType") or "")
            target_id = str(item.get("targetId") or "")
            slot = str(item.get("slot") or "")
            if target_type not in {"entity", "shot"} or not target_id:
                raise ProviderConfigurationError(
                    f"第 {position + 1} 个制作项缺少有效目标"
                )
            self._validate_production_run_target(
                project_id,
                episode_id,
                target_type=target_type,
                target_id=target_id,
                slot=slot,
            )
            key = (target_type, target_id, slot)
            if key in seen:
                raise ProviderConfigurationError(
                    f"制作项重复写入同一槽位：{target_type}/{target_id}/{slot}"
                )
            seen.add(key)
            request = item.get("request")
            if not isinstance(request, dict):
                raise ProviderConfigurationError(
                    f"第 {position + 1} 个制作项缺少生成请求"
                )
            task_type = str(request.get("taskType") or "")
            expected_task_type = _production_task_type(target_type, slot)
            if task_type != expected_task_type:
                raise ProviderConfigurationError(
                    f"{target_type}/{slot} 需要 {expected_task_type} 任务"
                )
            if not request.get("providerId") or not request.get("modelId"):
                raise ProviderConfigurationError(
                    f"第 {position + 1} 个制作项缺少模型路由"
                )
            normalized.append(
                {
                    "id": str(uuid.uuid4()),
                    "position": position,
                    "targetType": target_type,
                    "targetId": target_id,
                    "slot": slot,
                    "title": str(item.get("title") or f"制作项 {position + 1}"),
                    "request": request,
                }
            )
        run = self._repository.create_production_run(
            run_id=str(uuid.uuid4()),
            project_id=project_id,
            episode_id=episode_id,
            stage=stage,
            name=name.strip() or f"{episode.title} · {stage}",
            status="awaiting_approval" if requires_approval else "draft",
            requires_approval=requires_approval,
            max_parallel=max_parallel,
            items=normalized,
            planning=planning,
        )
        return self._production_run_view(run)

    def start_production_run(
        self,
        run_id: str,
        *,
        approved_by: str,
    ) -> dict[str, Any]:
        run = self._repository.get_production_run(run_id)
        if not run:
            raise ProviderConfigurationError("短剧制作运行不存在")
        if run.status not in {
            "draft",
            "awaiting_approval",
            "partial",
            "failed",
        }:
            return self._production_run_view(run)
        if run.requires_approval and not approved_by.strip():
            raise ProviderConfigurationError("开始制作前必须记录确认人")
        self._require_episode_ready_for_production(
            run.episode_id,
            stage=run.stage,
        )
        if self._production_media is None:
            raise ProviderConfigurationError("制作运行执行器未配置")
        updated = self._repository.update_production_run_status(
            run.id,
            status="queued",
            approved_by=approved_by.strip() or "local-user",
        )
        if not updated:
            raise ProviderConfigurationError("短剧制作运行不存在")
        self._schedule_production_run(run.id)
        return self._production_run_view(updated)

    def cancel_production_run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_production_run(run_id)
        if not run:
            raise ProviderConfigurationError("短剧制作运行不存在")
        if run.status in {"completed", "failed", "canceled"}:
            return self._production_run_view(run)
        updated = self._repository.update_production_run_status(
            run_id,
            status="canceled",
            completed=True,
        )
        if not updated:
            raise ProviderConfigurationError("短剧制作运行不存在")
        return self._production_run_view(updated)

    def retry_failed_production_run(
        self,
        run_id: str,
        *,
        approved_by: str,
    ) -> dict[str, Any]:
        run = self._repository.get_production_run(run_id)
        if not run:
            raise ProviderConfigurationError("短剧制作运行不存在")
        if run.status not in {"partial", "failed", "canceled"}:
            raise ProviderConfigurationError(
                "只有部分完成、失败或取消的制作运行可以重试"
            )
        self._require_episode_ready_for_production(
            run.episode_id,
            stage=run.stage,
        )
        if self._production_media is None:
            raise ProviderConfigurationError("制作运行执行器未配置")
        retried = self._repository.reset_failed_production_run_items(run_id)
        if not retried:
            raise ProviderConfigurationError("该制作运行没有失败任务")
        updated = self._repository.update_production_run_status(
            run_id,
            status="queued",
            approved_by=approved_by.strip() or "local-user",
        )
        if not updated:
            raise ProviderConfigurationError("短剧制作运行不存在")
        self._schedule_production_run(run_id)
        return self._production_run_view(updated)

    async def resume_production_runs(self) -> int:
        runs = self._repository.active_production_runs()
        for run in runs:
            self._schedule_production_run(run.id)
        return len(runs)

    def _schedule_production_run(self, run_id: str) -> None:
        task = asyncio.create_task(self._execute_production_run(run_id))
        self._run_tasks.add(task)
        task.add_done_callback(self._run_tasks.discard)

    async def _execute_production_run(self, run_id: str) -> None:
        run = self._repository.get_production_run(run_id)
        if not run or run.status in {"canceled", "completed", "failed"}:
            return
        self._repository.update_production_run_status(
            run_id,
            status="running",
            started=True,
        )
        items = self._repository.list_production_run_items(run_id)
        semaphore = asyncio.Semaphore(run.max_parallel)

        async def execute(item) -> None:
            async with semaphore:
                current = self._repository.get_production_run(run_id)
                if not current or current.status == "canceled":
                    return
                if item.status in {"succeeded", "skipped"}:
                    return
                try:
                    await self._execute_production_run_item(item)
                except Exception as exc:  # noqa: BLE001 - partial run result
                    self._repository.update_production_run_item(
                        item.id,
                        status="failed",
                        error=str(exc),
                    )

        await asyncio.gather(*(execute(item) for item in items))
        current = self._repository.get_production_run(run_id)
        if not current or current.status == "canceled":
            return
        final_items = self._repository.list_production_run_items(run_id)
        succeeded = sum(item.status == "succeeded" for item in final_items)
        failed = sum(item.status == "failed" for item in final_items)
        if failed == 0:
            status = "completed"
        elif succeeded == 0:
            status = "failed"
        else:
            status = "partial"
        self._repository.update_production_run_status(
            run_id,
            status=status,
            completed=True,
        )

    async def _execute_production_run_item(self, item) -> None:
        if self._production_media is None:
            raise ProviderConfigurationError("制作运行执行器未配置")
        task_id = item.generation_task_id
        if task_id:
            task = self._production_media.get(task_id)
            status = str(task.get("status") or "")
            if status in {"failed", "canceled"}:
                raise ProviderConfigurationError(
                    str(task.get("errorMessage") or "媒体任务失败")
                )
        else:
            run = self._repository.get_production_run(item.run_id)
            request = dict(item.request)
            if run:
                request["origin"] = {
                    "kind": "drama_production_run",
                    "projectId": run.project_id,
                    "episodeId": run.episode_id,
                    "productionRunId": run.id,
                    "stage": run.stage,
                    "targetType": item.target_type,
                    "targetId": item.target_id,
                    "slot": item.slot,
                }
            created = await self._production_media.submit(request)
            task_id = str(created.get("id") or "")
            if not task_id:
                raise ProviderConfigurationError("媒体任务未返回任务 ID")
            self._repository.update_production_run_item(
                item.id,
                status="queued",
                generation_task_id=task_id,
            )
        self._repository.update_production_run_item(
            item.id,
            status="running",
        )
        completed = await self._wait_production_media_task(item.run_id, task_id)
        if not completed:
            raise ProviderConfigurationError("制作运行已取消")
        assets = completed.get("resultAssetIds")
        asset_id = (
            str(assets[0])
            if isinstance(assets, list) and assets
            else ""
        )
        if not asset_id:
            raise ProviderConfigurationError("媒体任务完成但没有返回素材")
        if item.target_type == "shot":
            self.bind_shot_asset(
                item.target_id,
                slot=item.slot,
                asset_id=asset_id,
            )
        else:
            self.bind_entity_asset(
                item.target_id,
                slot=item.slot,
                asset_id=asset_id,
            )
        self._repository.update_production_run_item(
            item.id,
            status="succeeded",
            result_asset_id=asset_id,
            error="",
        )

    async def _wait_production_media_task(
        self,
        run_id: str,
        task_id: str,
    ) -> dict[str, Any] | None:
        if self._production_media is None:
            return None
        for _ in range(1800):
            run = self._repository.get_production_run(run_id)
            if not run or run.status == "canceled":
                return None
            task = self._production_media.get(task_id)
            status = str(task.get("status") or "")
            if status in {"succeeded", "completed"}:
                return task
            if status in {"failed", "canceled"}:
                raise ProviderConfigurationError(
                    str(task.get("errorMessage") or "媒体任务失败")
                )
            await asyncio.sleep(2)
        raise ProviderConfigurationError("媒体任务等待超时")

    def _production_run_view(self, run) -> dict[str, Any]:
        items = self._repository.list_production_run_items(run.id)
        counts = {
            status: sum(item.status == status for item in items)
            for status in DRAMA_RUN_ITEM_STATUSES
        }
        return {
            "id": run.id,
            "projectId": run.project_id,
            "episodeId": run.episode_id,
            "stage": run.stage,
            "name": run.name,
            "status": run.status,
            "requiresApproval": run.requires_approval,
            "maxParallel": run.max_parallel,
            "approvedBy": run.approved_by,
            "startedAt": run.started_at,
            "completedAt": run.completed_at,
            "planning": run.planning,
            "createdAt": run.created_at,
            "updatedAt": run.updated_at,
            "counts": counts,
            "items": [
                {
                    "id": item.id,
                    "position": item.position,
                    "targetType": item.target_type,
                    "targetId": item.target_id,
                    "slot": item.slot,
                    "title": item.title,
                    "status": item.status,
                    "generationTaskId": item.generation_task_id,
                    "resultAssetId": item.result_asset_id,
                    "error": item.error,
                    "request": item.request,
                    "createdAt": item.created_at,
                    "updatedAt": item.updated_at,
                }
                for item in items
            ],
        }

    def _validate_production_run_target(
        self,
        project_id: str,
        episode_id: str,
        *,
        target_type: str,
        target_id: str,
        slot: str,
    ) -> None:
        if not slot:
            raise ProviderConfigurationError("制作项缺少语义槽位")
        if target_type == "shot":
            shot = self._repository.get_shot(target_id)
            if not shot:
                raise ProviderConfigurationError("制作项镜头不存在")
            scene = self._repository.get_scene(shot.scene_id)
            if not scene or scene.episode_id != episode_id:
                raise ProviderConfigurationError("制作项镜头不属于当前分集")
        else:
            entity = self._repository.get_entity(target_id)
            if not entity or entity.project_id != project_id:
                raise ProviderConfigurationError("制作项实体不属于当前项目")
        _production_task_type(target_type, slot)

    def _require_episode_ready_for_production(
        self,
        episode_id: str,
        *,
        stage: str,
    ) -> None:
        audit = self.audit_episode(episode_id)
        ready = (
            audit["readyForVideo"]
            if stage == "clips"
            else audit["readyForAssets"]
        )
        if ready:
            return
        blocking_codes = (
            {"shot_assets_unbound"}
            if stage == "clips"
            else set()
        )
        blockers = [
            issue["message"]
            for issue in audit["issues"]
            if issue["severity"] == "error"
            or issue["code"] in blocking_codes
        ]
        detail = "；".join(blockers[:4]) or "分集计划或镜头引用不完整"
        raise ProviderConfigurationError(
            f"分集检查未通过，暂不能创建该阶段制作运行：{detail}"
        )

    def bind_entity_asset(
        self,
        entity_id: str,
        *,
        slot: str,
        asset_id: str,
    ) -> dict[str, Any]:
        entity = self._repository.get_entity(entity_id)
        if not entity:
            raise ProviderConfigurationError("短剧实体不存在")
        self._require_asset_type(asset_id, "image")
        normalized_slot = slot.strip()
        if normalized_slot == "primary":
            primary_asset_id = asset_id
            references = tuple(
                value
                for value in entity.reference_asset_ids
                if value != asset_id
            )
            slots = dict(entity.asset_slots)
        elif normalized_slot == "reference":
            primary_asset_id = entity.primary_asset_id
            references = tuple(
                dict.fromkeys((*entity.reference_asset_ids, asset_id))
            )
            if len(references) > 10:
                raise ProviderConfigurationError("补充参考最多绑定 10 张图片")
            slots = dict(entity.asset_slots)
        else:
            if not normalized_slot:
                raise ProviderConfigurationError("资产槽位不能为空")
            primary_asset_id = entity.primary_asset_id
            references = entity.reference_asset_ids
            slots = {**entity.asset_slots, normalized_slot: asset_id}
        updated = self._repository.update_entity(
            entity.id,
            name=entity.name,
            description=entity.description,
            status=entity.status,
            primary_asset_id=primary_asset_id,
            reference_asset_ids=list(references),
            asset_slots=slots,
            profile=entity.profile,
            voice_name=entity.voice_name,
            voice_rate=entity.voice_rate,
        )
        if not updated:
            raise ProviderConfigurationError("短剧实体不存在")
        self._record_entity_candidates(
            updated,
            primary_asset_id=primary_asset_id,
            reference_asset_ids=list(references),
            asset_slots=slots,
        )
        self._touch_stages(
            updated.project_id,
            "assets",
            "keyframes",
            "clips",
            "timeline",
            reason=f"替换实体槽位“{normalized_slot}”",
        )
        return self._entity_with_candidates(updated)

    def bind_shot_asset(
        self,
        shot_id: str,
        *,
        slot: str,
        asset_id: str,
    ) -> dict[str, Any]:
        shot = self._repository.get_shot(shot_id)
        if not shot:
            raise ProviderConfigurationError("短剧镜头不存在")
        normalized_slot = slot.strip()
        field_by_slot = {
            "first_frame": "first_frame_asset_id",
            "last_frame": "last_frame_asset_id",
            "grid9": "grid9_asset_id",
            "storyboard": "storyboard_asset_id",
            "video": "video_asset_id",
            "audio": "audio_asset_id",
        }
        field = field_by_slot.get(normalized_slot)
        if not field:
            raise ProviderConfigurationError("未知的镜头资产槽位")
        expected_type = "video" if normalized_slot == "video" else (
            "audio" if normalized_slot == "audio" else "image"
        )
        self._require_asset_type(asset_id, expected_type)
        status = None
        if normalized_slot == "video":
            status = "clip_ready"
        elif normalized_slot in {
            "first_frame",
            "last_frame",
            "grid9",
            "storyboard",
        }:
            status = (
                "clip_ready"
                if shot.video_asset_id
                else "keyframe_ready"
            )
        elif normalized_slot == "audio" and shot.status == "approved":
            status = "clip_ready"
        updated = self._repository.update_shot(
            shot_id,
            status=status,
            **{field: asset_id},
        )
        if not updated:
            raise ProviderConfigurationError("短剧镜头不存在")
        if updated.status != shot.status:
            self._record_shot_status_event(
                updated.id,
                from_status=shot.status,
                to_status=updated.status,
                reviewer="system",
                note=f"素材槽位 {normalized_slot} 更新",
            )
        self._record_shot_candidate(updated, normalized_slot, asset_id)
        scene = self._repository.get_scene(updated.scene_id)
        episode = (
            self._repository.get_episode(scene.episode_id) if scene else None
        )
        if episode:
            self._touch_stages(
                episode.project_id,
                "keyframes",
                "clips",
                "timeline",
                reason=f"替换镜头槽位“{normalized_slot}”",
            )
        return self._shot_with_candidates(updated)

    def list_reviews(
        self,
        project_id: str,
        *,
        stage: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        if stage is not None and stage not in DRAMA_STAGES:
            raise ProviderConfigurationError("未知的短剧制作阶段")
        return [
            _review_view(review)
            for review in self._repository.list_reviews(
                project_id,
                stage=stage,
            )
        ]

    def record_review(
        self,
        project_id: str,
        *,
        stage: str,
        role_id: str,
        status: str,
        score: float,
        checklist: list[dict[str, object]],
        feedback: str,
        reviewer: str,
    ) -> dict[str, Any]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        if stage not in DRAMA_STAGES:
            raise ProviderConfigurationError("未知的短剧制作阶段")
        role_ids = {role.id for role in DRAMA_PRODUCTION_ROLES}
        if role_id not in role_ids and role_id != "stage_gate":
            raise ProviderConfigurationError("未知的短剧制作角色")
        if status not in DRAMA_REVIEW_STATUSES:
            raise ProviderConfigurationError("未知的审核状态")
        if reviewer not in {"agent", "user", "system"}:
            raise ProviderConfigurationError("未知的审核来源")
        if not 0 <= score <= 100:
            raise ProviderConfigurationError("审核分数必须在 0–100 之间")
        checks = [
            DramaReviewCheck(
                key=str(item.get("key") or "").strip(),
                label=str(item.get("label") or "").strip(),
                passed=bool(item.get("passed")),
                note=str(item.get("note") or "").strip(),
            )
            for item in checklist
            if str(item.get("key") or "").strip()
            and str(item.get("label") or "").strip()
        ]
        review = self._repository.create_review(
            review_id=str(uuid.uuid4()),
            project_id=project_id,
            stage=stage,
            role_id=role_id,
            status=status,
            score=score,
            checklist=checks,
            feedback=feedback.strip(),
            reviewer=reviewer,
            artifact_revision=self._repository.get_stage_revision(
                project_id,
                stage,
            ).revision,
        )
        return _review_view(review)

    def decide_stage(
        self,
        project_id: str,
        *,
        stage: str,
        approved: bool,
        feedback: str,
    ) -> dict[str, Any]:
        if stage not in DRAMA_STAGES:
            raise ProviderConfigurationError("未知的短剧制作阶段")
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        revision_state = self._repository.get_stage_revision(
            project_id,
            stage,
        )
        gate_before = _stage_gate_view(
            stage,
            reviews=self._repository.list_reviews(project_id, stage=stage),
            current_revision=revision_state.revision,
            approved_revision=revision_state.approved_revision,
            last_change_reason=revision_state.last_change_reason,
        )
        if approved and not gate_before["agentReady"]:
            raise ProviderConfigurationError(
                "当前修订尚未完成全部角色审核；请先重新审核再确认本阶段"
            )
        review = self.record_review(
            project_id,
            stage=stage,
            role_id="stage_gate",
            status="passed" if approved else "changes_requested",
            score=100 if approved else 0,
            checklist=[],
            feedback=feedback,
            reviewer="user",
        )
        self._repository.set_stage_approval(
            project_id,
            stage=stage,
            approved=approved,
            approved_by="user",
        )
        approved_revision = self._repository.get_stage_revision(
            project_id,
            stage,
        ).approved_revision
        gate = _stage_gate_view(
            stage,
            reviews=self._repository.list_reviews(project_id, stage=stage),
            current_revision=self._repository.get_stage_revision(
                project_id,
                stage,
            ).revision,
            approved_revision=approved_revision,
            last_change_reason=self._repository.get_stage_revision(
                project_id,
                stage,
            ).last_change_reason,
        )
        gate["decision"] = review
        if approved:
            next_index = min(DRAMA_STAGES.index(stage) + 1, len(DRAMA_STAGES) - 1)
            if stage != DRAMA_STAGES[-1]:
                self.update_stage(
                    project_id,
                    active_stage=DRAMA_STAGES[next_index],
                    status="in_progress",
                )
        return gate

    def plan_episodes(
        self,
        project_id: str,
        episodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        if not episodes:
            raise ProviderConfigurationError("至少需要一个分集计划")
        existing = {
            episode.id: episode
            for episode in self._repository.list_episodes(project_id)
        }
        normalized: list[
            tuple[dict[str, Any], DramaEpisode | None, DramaEpisodePlan]
        ] = []
        for index, item in enumerate(episodes):
            episode_id = str(item.get("episodeId") or "")
            if episode_id:
                episode = existing.get(episode_id)
                if not episode:
                    raise ProviderConfigurationError(
                        f"第 {index + 1} 个分集不属于当前项目"
                    )
            else:
                episode = None
                if not str(item.get("title") or "").strip():
                    raise ProviderConfigurationError(
                        f"第 {index + 1} 个分集缺少标题"
                    )
            normalized.append((item, episode, _episode_plan_from_mapping(item)))
        saved: list[dict[str, Any]] = []
        for source, episode, plan in normalized:
            if episode:
                saved.append(self.update_episode_plan(episode.id, plan))
            else:
                saved.append(
                    self.create_episode(
                        project_id,
                        title=str(source.get("title") or ""),
                        synopsis=str(source.get("synopsis") or ""),
                        plan=plan,
                    )
                )
        return saved

    def plan_episode_shots(
        self,
        episode_id: str,
        scenes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        episode = self._repository.get_episode(episode_id)
        if not episode:
            raise ProviderConfigurationError("短剧分集不存在")
        if self._repository.list_scenes(episode_id):
            raise ProviderConfigurationError(
                "本集已有场次。请先审阅现有拆解，不要用 Agent 计划覆盖用户内容。"
            )
        if not scenes:
            raise ProviderConfigurationError("至少需要一个场次计划")
        for scene_index, scene in enumerate(scenes):
            if not str(scene.get("heading") or "").strip():
                raise ProviderConfigurationError(
                    f"第 {scene_index + 1} 个场次缺少标题"
                )
            shots = scene.get("shots") or []
            if not isinstance(shots, list):
                raise ProviderConfigurationError("镜头计划必须是数组")
            for shot_index, shot in enumerate(shots):
                if not str(shot.get("title") or "").strip():
                    raise ProviderConfigurationError(
                        f"场次 {scene_index + 1} 的镜头 "
                        f"{shot_index + 1} 缺少标题"
                    )
        created_scenes: list[dict[str, Any]] = []
        for scene_payload in scenes:
            scene = self.create_scene(
                episode_id,
                heading=str(scene_payload.get("heading") or ""),
                summary=str(scene_payload.get("summary") or ""),
                script_document_id=(
                    str(scene_payload.get("scriptDocumentId"))
                    if scene_payload.get("scriptDocumentId")
                    else None
                ),
            )
            scene_shots = [
                self.create_shot(
                    scene["id"],
                    title=str(shot.get("title") or ""),
                    description=str(shot.get("description") or ""),
                    dialogue=str(shot.get("dialogue") or ""),
                    duration_seconds=float(shot.get("durationSeconds") or 5),
                    direction=_string_mapping(shot.get("direction")),
                )
                for shot in scene_payload.get("shots") or []
            ]
            created_scenes.append({**scene, "shots": scene_shots})
        return {
            "episodeId": episode_id,
            "scenes": created_scenes,
            "sceneCount": len(created_scenes),
            "shotCount": sum(
                len(scene["shots"]) for scene in created_scenes
            ),
        }

    def plan_assets(
        self,
        project_id: str,
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self._repository.get_project(project_id):
            raise ProviderConfigurationError("短剧项目不存在")
        existing = {
            (entity.kind, entity.name.casefold()): entity
            for entity in self._repository.list_entities(project_id)
        }
        saved: list[dict[str, Any]] = []
        for index, payload in enumerate(entities):
            kind = str(payload.get("kind") or "")
            name = str(payload.get("name") or "").strip()
            if kind not in DRAMA_ENTITY_KINDS or not name:
                raise ProviderConfigurationError(
                    f"第 {index + 1} 个资产缺少有效类型或名称"
                )
            current = existing.get((kind, name.casefold()))
            profile_payload = payload.get("profile")
            profile = (
                _string_mapping(profile_payload)
                if profile_payload is not None
                else None
            )
            if current:
                updated = self.update_entity(
                    current.id,
                    name=current.name,
                    description=str(
                        payload.get("description") or current.description
                    ),
                    status=current.status,
                    primary_asset_id=current.primary_asset_id,
                    reference_asset_ids=list(current.reference_asset_ids),
                    asset_slots={
                        **current.asset_slots,
                        **_string_mapping(payload.get("assetSlots")),
                    },
                    profile=profile,
                    voice_name=current.voice_name,
                    voice_rate=current.voice_rate,
                )
            else:
                created = self.create_entity(
                    project_id,
                    kind=kind,
                    name=name,
                    description=str(payload.get("description") or ""),
                    profile=profile,
                )
                updated = self.update_entity(
                    created["id"],
                    name=created["name"],
                    description=created["description"],
                    status="draft",
                    primary_asset_id=None,
                    reference_asset_ids=[],
                    asset_slots=_string_mapping(payload.get("assetSlots")),
                    profile=profile,
                )
            if updated:
                saved.append(updated)
        return saved

    def _shot_with_candidates(self, shot) -> dict[str, Any]:
        scene = self._repository.get_scene(shot.scene_id)
        episode = (
            self._repository.get_episode(scene.episode_id) if scene else None
        )
        candidates = (
            self._repository.list_asset_candidates(
                episode.project_id,
                subject_type="shot",
                subject_id=shot.id,
            )
            if episode
            else []
        )
        status_events = self._repository.list_shot_status_events(
            shot.id,
            limit=20,
        )
        return {
            **_shot_view(shot),
            "entityReferences": [
                {
                    "entityId": reference.entity_id,
                    "role": reference.role,
                }
                for reference in self._repository.list_shot_references(
                    shot.id
                )
            ],
            "candidates": [
                _asset_candidate_view(candidate)
                for candidate in candidates
            ],
            "statusHistory": [
                _shot_status_event_view(event)
                for event in status_events
            ],
        }

    def _entity_with_candidates(self, entity) -> dict[str, Any]:
        return {
            **_entity_view(entity),
            "candidates": [
                _asset_candidate_view(candidate)
                for candidate in self._repository.list_asset_candidates(
                    entity.project_id,
                    subject_type="entity",
                    subject_id=entity.id,
                )
            ],
        }

    def _touch_stages(
        self,
        project_id: str,
        *stages: str,
        reason: str,
    ) -> None:
        self._repository.touch_stage_revisions(
            project_id,
            stages=list(stages),
            reason=reason,
        )

    def _record_shot_candidate(
        self,
        shot,
        slot: str,
        asset_id: str,
    ) -> None:
        scene = self._repository.get_scene(shot.scene_id)
        episode = (
            self._repository.get_episode(scene.episode_id) if scene else None
        )
        if not episode:
            return
        self._repository.record_asset_candidate(
            candidate_id=str(uuid.uuid4()),
            project_id=episode.project_id,
            subject_type="shot",
            subject_id=shot.id,
            slot=slot,
            asset_id=asset_id,
            source="binding",
        )

    def _record_shot_status_event(
        self,
        shot_id: str,
        *,
        from_status: str,
        to_status: str,
        reviewer: str,
        note: str,
    ) -> None:
        self._repository.create_shot_status_event(
            event_id=str(uuid.uuid4()),
            shot_id=shot_id,
            from_status=from_status,
            to_status=to_status,
            reviewer=reviewer,
            note=note,
        )

    def _record_entity_candidates(
        self,
        entity,
        *,
        primary_asset_id: str | None,
        reference_asset_ids: list[str],
        asset_slots: dict[str, str],
    ) -> None:
        if primary_asset_id:
            self._repository.record_asset_candidate(
                candidate_id=str(uuid.uuid4()),
                project_id=entity.project_id,
                subject_type="entity",
                subject_id=entity.id,
                slot="primary",
                asset_id=primary_asset_id,
                source="binding",
            )
        for asset_id in dict.fromkeys(reference_asset_ids):
            self._repository.record_asset_candidate(
                candidate_id=str(uuid.uuid4()),
                project_id=entity.project_id,
                subject_type="entity",
                subject_id=entity.id,
                slot="reference",
                asset_id=asset_id,
                source="binding",
            )
        for slot, asset_id in asset_slots.items():
            if slot and asset_id:
                self._repository.record_asset_candidate(
                    candidate_id=str(uuid.uuid4()),
                    project_id=entity.project_id,
                    subject_type="entity",
                    subject_id=entity.id,
                    slot=slot,
                    asset_id=asset_id,
                    source="binding",
                )

    def _require_asset_type(self, asset_id: str, expected_type: str) -> None:
        asset = self._assets.get(asset_id)
        actual_type = str(asset.get("type") or "")
        if actual_type != expected_type:
            raise ProviderConfigurationError(
                f"槽位需要 {expected_type} 素材，当前素材类型为"
                f" {actual_type or 'unknown'}"
            )


def _project_view(project: DramaProject) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "idea": project.idea,
        "format": project.format,
        "visualStyle": project.visual_style,
        "status": project.status,
        "activeStage": project.active_stage,
        "workspace": project.workspace_path,
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
        "stages": list(DRAMA_STAGES),
    }


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _document_view(document: DramaDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "projectId": document.project_id,
        "kind": document.kind,
        "version": document.version,
        "status": document.status,
        "title": document.title,
        "content": document.content,
        "createdAt": document.created_at,
        "updatedAt": document.updated_at,
    }


def _episode_view(episode) -> dict[str, Any]:
    return {
        "id": episode.id,
        "projectId": episode.project_id,
        "episodeNumber": episode.episode_number,
        "title": episode.title,
        "synopsis": episode.synopsis,
        "status": episode.status,
        "exportAssetId": episode.export_asset_id,
        "exportManifestId": episode.export_manifest_id,
        "subtitleCues": [
            _subtitle_view(cue) for cue in episode.subtitle_cues
        ],
        "subtitleStyle": _subtitle_style_view(episode.subtitle_style),
        "audioMix": _audio_mix_view(episode.audio_mix),
        "plan": _episode_plan_view(episode.plan),
        "createdAt": episode.created_at,
        "updatedAt": episode.updated_at,
    }


def _scene_view(scene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "episodeId": scene.episode_id,
        "sceneNumber": scene.scene_number,
        "heading": scene.heading,
        "summary": scene.summary,
        "scriptDocumentId": scene.script_document_id,
        "status": scene.status,
        "createdAt": scene.created_at,
        "updatedAt": scene.updated_at,
    }


def _shot_view(shot) -> dict[str, Any]:
    return {
        "id": shot.id,
        "sceneId": shot.scene_id,
        "shotNumber": shot.shot_number,
        "title": shot.title,
        "description": shot.description,
        "dialogue": shot.dialogue,
        "durationSeconds": shot.duration_seconds,
        "status": shot.status,
        "firstFrameAssetId": shot.first_frame_asset_id,
        "lastFrameAssetId": shot.last_frame_asset_id,
        "grid9AssetId": shot.grid9_asset_id,
        "storyboardAssetId": shot.storyboard_asset_id,
        "videoAssetId": shot.video_asset_id,
        "audioAssetId": shot.audio_asset_id,
        "promptOverrides": dict(shot.prompt_overrides),
        "direction": dict(shot.direction),
        "createdAt": shot.created_at,
        "updatedAt": shot.updated_at,
    }


def _asset_candidate_view(candidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "projectId": candidate.project_id,
        "subjectType": candidate.subject_type,
        "subjectId": candidate.subject_id,
        "slot": candidate.slot,
        "assetId": candidate.asset_id,
        "status": candidate.status,
        "source": candidate.source,
        "createdAt": candidate.created_at,
        "updatedAt": candidate.updated_at,
    }


def _shot_status_event_view(event) -> dict[str, Any]:
    return {
        "id": event.id,
        "shotId": event.shot_id,
        "fromStatus": event.from_status,
        "toStatus": event.to_status,
        "reviewer": event.reviewer,
        "note": event.note,
        "createdAt": event.created_at,
    }


def _production_task_type(target_type: str, slot: str) -> str:
    if target_type == "entity":
        return "image_generation"
    if slot == "video":
        return "video_generation"
    if slot == "audio":
        return "audio_processing"
    if slot in {
        "first_frame",
        "last_frame",
        "grid9",
        "storyboard",
    }:
        return "image_generation"
    raise ProviderConfigurationError("未知的制作项目标槽位")


def _document_stage(kind: str) -> str:
    return {
        "brief": "brief",
        "story_bible": "bible",
        "script": "script",
    }[kind]


def _entity_view(entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "projectId": entity.project_id,
        "kind": entity.kind,
        "name": entity.name,
        "description": entity.description,
        "status": entity.status,
        "primaryAssetId": entity.primary_asset_id,
        "referenceAssetIds": list(entity.reference_asset_ids),
        "assetSlots": dict(entity.asset_slots),
        "assetPrompts": dict(entity.asset_prompts),
        "profile": dict(entity.profile),
        "voiceName": entity.voice_name,
        "voiceRate": entity.voice_rate,
        "createdAt": entity.created_at,
        "updatedAt": entity.updated_at,
    }


def _subtitle_view(cue: DramaSubtitleCue) -> dict[str, Any]:
    return {
        "startSeconds": cue.start_seconds,
        "endSeconds": cue.end_seconds,
        "text": cue.text,
    }


def _normalize_subtitles(
    cues: list[dict[str, object]],
) -> list[DramaSubtitleCue]:
    normalized: list[DramaSubtitleCue] = []
    for index, cue in enumerate(cues):
        start = float(cue.get("startSeconds") or 0)
        end = float(cue.get("endSeconds") or 0)
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        if start < 0 or end <= start:
            raise ProviderConfigurationError(
                f"第 {index + 1} 条字幕时间范围无效"
            )
        normalized.append(
            DramaSubtitleCue(
                start_seconds=start,
                end_seconds=end,
                text=text,
            )
        )
    return normalized


def _audio_mix_view(mix: DramaAudioMix) -> dict[str, Any]:
    return {
        "soundEffects": [
            {
                "assetId": effect.asset_id,
                "startSeconds": effect.start_seconds,
                "durationSeconds": effect.duration_seconds,
                "volumeDb": effect.volume_db,
            }
            for effect in mix.sound_effects
        ],
        "musicAssetId": mix.music_asset_id,
        "musicVolumeDb": mix.music_volume_db,
        "ambienceAssetId": mix.ambience_asset_id,
        "ambienceVolumeDb": mix.ambience_volume_db,
        "ducking": mix.ducking,
    }


def _subtitle_style_view(style: DramaSubtitleStyle) -> dict[str, Any]:
    return {
        "preset": style.preset,
        "fontSize": style.font_size,
        "outline": style.outline,
        "marginV": style.margin_v,
        "primaryColor": style.primary_color,
        "outlineColor": style.outline_color,
    }


def _script_craft_analysis(content: str) -> dict[str, Any]:
    """Return deterministic craft signals for Agent-led script revision."""

    scene_pattern = re.compile(
        r"(?m)^\s*(?:#{1,4}\s*)?(?:场|场景)\s*(\d+(?:-\d+)?)[^\n]*"
    )
    dialogue_pattern = re.compile(r"^([^：:\n]{1,30})[：:]\s*(.+)$")
    matches = list(scene_pattern.finditer(content))
    scenes: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    all_dialogue_lengths: list[int] = []
    repeated_dialogue: dict[str, int] = {}
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(content)
        )
        block_lines = [
            line.strip()
            for line in content[block_start:block_end].splitlines()
            if line.strip()
        ]
        heading = content[match.start():block_end].splitlines()[0].strip()
        heading = re.sub(r"^#{1,4}\s*", "", heading)
        scene_number = int(match.group(1).split("-")[0])
        dialogue_texts: list[str] = []
        action_line_count = 0
        current_run = 0
        max_dialogue_run = 0
        for line in block_lines:
            if dialogue_match := dialogue_pattern.match(line):
                dialogue_text = dialogue_match.group(2).strip()
                dialogue_texts.append(dialogue_text)
                normalized = re.sub(r"\s+", "", dialogue_text)
                dialogue_length = len(normalized)
                all_dialogue_lengths.append(dialogue_length)
                repeated_dialogue[normalized] = (
                    repeated_dialogue.get(normalized, 0) + 1
                )
                current_run += 1
                max_dialogue_run = max(max_dialogue_run, current_run)
            elif not re.match(
                r"^第\s*\d+\s*集|^(?:场|场景)\s*\d+",
                line,
            ):
                action_line_count += 1
                current_run = 0
        longest_dialogue = max(
            (
                len(re.sub(r"\s+", "", dialogue))
                for dialogue in dialogue_texts
            ),
            default=0,
        )
        scenes.append(
            {
                "sceneNumber": scene_number,
                "heading": heading,
                "actionLineCount": action_line_count,
                "dialogueLineCount": len(dialogue_texts),
                "longestDialogueChars": longest_dialogue,
                "maxConsecutiveDialogue": max_dialogue_run,
            }
        )
        if dialogue_texts and action_line_count == 0:
            issues.append(
                {
                    "code": "script_scene_action_missing",
                    "sceneNumber": scene_number,
                    "message": (
                        f"场次“{heading}”只有对白，没有可表演的动作、空间或反应描写"
                    ),
                }
            )
        if longest_dialogue >= 80:
            issues.append(
                {
                    "code": "script_dialogue_overwritten",
                    "sceneNumber": scene_number,
                    "message": (
                        f"场次“{heading}”存在 {longest_dialogue} 字长对白，"
                        "优先删解释、拆成动作反应或潜台词"
                    ),
                }
            )
        if max_dialogue_run >= 6:
            issues.append(
                {
                    "code": "script_dialogue_run_long",
                    "sceneNumber": scene_number,
                    "message": (
                        f"场次“{heading}”连续 {max_dialogue_run} 行对白，"
                        "缺少动作、停顿或视觉信息"
                    ),
                }
            )
    repeated_count = sum(
        count - 1
        for text, count in repeated_dialogue.items()
        if text and count > 1
    )
    return {
        "summary": {
            "sceneCount": len(scenes),
            "dialogueLineCount": len(all_dialogue_lengths),
            "averageDialogueChars": (
                round(
                    sum(all_dialogue_lengths) / len(all_dialogue_lengths),
                    1,
                )
                if all_dialogue_lengths
                else 0
            ),
            "longestDialogueChars": max(all_dialogue_lengths, default=0),
            "repeatedDialogueLineCount": repeated_count,
            "overwrittenDialogueCount": sum(
                issue["code"] == "script_dialogue_overwritten"
                for issue in issues
            ),
            "actionlessDialogueSceneCount": sum(
                issue["code"] == "script_scene_action_missing"
                for issue in issues
            ),
            "longDialogueRunSceneCount": sum(
                issue["code"] == "script_dialogue_run_long"
                for issue in issues
            ),
        },
        "scenes": scenes,
        "issues": issues,
    }


def _audit_issue(
    severity: str,
    code: str,
    message: str,
    *,
    shot_id: str | None = None,
    entity_id: str | None = None,
    scene_number: int | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "shotId": shot_id,
        "entityId": entity_id,
        "sceneNumber": scene_number,
    }


def _dialogue_speaker(dialogue: str) -> str:
    for line in dialogue.splitlines():
        match = re.match(r"^\s*([^：:\n]{1,30})[：:]", line)
        if match:
            return match.group(1).strip()
    return ""


def _normalized_speaker_name(value: str) -> str:
    """Normalize delivery notes without changing the stored screenplay."""
    without_notes = re.sub(r"[（(][^）)]*[）)]", "", value)
    return re.sub(r"\s+", "", without_notes).strip()


def _role_view(role) -> dict[str, Any]:
    return {
        "id": role.id,
        "title": role.title,
        "department": role.department,
        "description": role.description,
        "stageIds": list(role.stage_ids),
        "responsibilities": list(role.responsibilities),
        "requiredInputs": list(role.required_inputs),
        "deliverables": list(role.deliverables),
        "checklist": list(role.checklist),
        "reviewCriteria": list(role.review_criteria),
    }


def _review_view(review: DramaReview) -> dict[str, Any]:
    return {
        "id": review.id,
        "projectId": review.project_id,
        "stage": review.stage,
        "roleId": review.role_id,
        "status": review.status,
        "score": review.score,
        "checklist": [
            {
                "key": item.key,
                "label": item.label,
                "passed": item.passed,
                "note": item.note,
            }
            for item in review.checklist
        ],
        "feedback": review.feedback,
        "reviewer": review.reviewer,
        "artifactRevision": review.artifact_revision,
        "createdAt": review.created_at,
        "updatedAt": review.updated_at,
    }


def _stage_gate_view(
    stage: str,
    *,
    reviews: list[DramaReview],
    current_revision: int,
    approved_revision: int | None,
    last_change_reason: str,
) -> dict[str, Any]:
    role_ids = DRAMA_STAGE_OWNERS[stage]
    roles_by_id = {role.id: role for role in DRAMA_PRODUCTION_ROLES}
    current_reviews = [
        review
        for review in reviews
        if review.artifact_revision == current_revision
    ]
    latest_by_role: dict[str, DramaReview] = {}
    for review in current_reviews:
        if review.role_id in role_ids:
            latest_by_role[review.role_id] = review
    user_decisions = [
        review
        for review in current_reviews
        if review.role_id == "stage_gate" and review.reviewer == "user"
    ]
    latest_decision = user_decisions[-1] if user_decisions else None
    stale = (
        approved_revision is not None
        and approved_revision < current_revision
    )
    statuses = [review.status for review in latest_by_role.values()]
    if stale:
        status = "changes_requested"
        label = "上游内容已变更，需要重新确认"
    elif (
        latest_decision
        and latest_decision.status == "passed"
        and approved_revision == current_revision
    ):
        status = "approved"
        label = "已由用户确认"
    elif latest_decision and latest_decision.status == "changes_requested":
        status = "changes_requested"
        label = "用户要求修改"
    elif "failed" in statuses:
        status = "failed"
        label = "审核未通过"
    elif "changes_requested" in statuses:
        status = "changes_requested"
        label = "Agent 发现问题"
    elif role_ids and all(role_id in latest_by_role for role_id in role_ids):
        status = "awaiting_user"
        label = "等待用户确认"
    elif latest_by_role:
        status = "in_review"
        label = "正在审核"
    else:
        status = "pending"
        label = "尚未审核"
    scores = [review.score for review in latest_by_role.values()]
    return {
        "stage": stage,
        "ownerRoleIds": list(role_ids),
        "owners": [
            {
                "id": role_id,
                "title": roles_by_id[role_id].title,
                "department": roles_by_id[role_id].department,
            }
            for role_id in role_ids
            if role_id in roles_by_id
        ],
        "status": status,
        "label": label,
        "revision": current_revision,
        "approvedRevision": approved_revision,
        "stale": stale,
        "lastChangeReason": last_change_reason,
        "score": round(sum(scores) / len(scores), 1) if scores else None,
        "approved": status == "approved",
        "agentReady": bool(role_ids)
        and all(role_id in latest_by_role for role_id in role_ids)
        and not any(
            status in {"failed", "changes_requested"} for status in statuses
        ),
        "latestReviews": {
            role_id: _review_view(review)
            for role_id, review in latest_by_role.items()
        },
        "userDecision": (
            _review_view(latest_decision) if latest_decision else None
        ),
    }


def _episode_plan_view(plan: DramaEpisodePlan) -> dict[str, Any]:
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


def _episode_plan_complete(plan: DramaEpisodePlan) -> bool:
    return all(
        (
            plan.time_scope.strip(),
            plan.locations,
            plan.interior_exterior,
            plan.characters,
            plan.scenes,
            plan.story_beats,
            plan.visual_requirements,
            plan.dialogue_requirements,
        )
    )


def _episode_plan_from_mapping(payload: dict[str, Any]) -> DramaEpisodePlan:
    return DramaEpisodePlan(
        time_scope=str(payload.get("timeScope") or "").strip(),
        locations=_string_list(payload.get("locations")),
        interior_exterior=_string_list(payload.get("interiorExterior")),
        characters=_string_list(payload.get("characters")),
        scenes=_string_list(payload.get("scenes")),
        story_beats=_string_list(payload.get("storyBeats")),
        visual_requirements=_string_list(
            payload.get("visualRequirements")
        ),
        dialogue_requirements=_string_list(
            payload.get("dialogueRequirements")
        ),
        continuity_risks=_string_list(payload.get("continuityRisks")),
        scene_contracts=_scene_contracts_from_mapping(
            payload.get("sceneContracts")
        ),
    )


def _scene_contracts_from_mapping(value: object) -> tuple[DramaSceneContract, ...]:
    if not isinstance(value, list):
        return ()
    contracts: list[DramaSceneContract] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            scene_number = int(item.get("sceneNumber") or 0)
        except (TypeError, ValueError):
            continue
        if scene_number <= 0:
            continue
        contracts.append(
            DramaSceneContract(
                scene_number=scene_number,
                title=str(item.get("title") or "").strip(),
                value_in=str(item.get("valueIn") or "").strip(),
                character_objectives=_string_list(
                    item.get("characterObjectives")
                ),
                obstacle=str(item.get("obstacle") or "").strip(),
                tactics=_string_list(item.get("tactics")),
                beats=_string_list(item.get("beats")),
                turn=str(item.get("turn") or "").strip(),
                value_out=str(item.get("valueOut") or "").strip(),
                subtext=str(item.get("subtext") or "").strip(),
                visual_strategy=str(
                    item.get("visualStrategy") or ""
                ).strip(),
                performance_notes=str(
                    item.get("performanceNotes") or ""
                ).strip(),
                sound_notes=str(item.get("soundNotes") or "").strip(),
            )
        )
    return tuple(contracts)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        str(item).strip() for item in value if str(item).strip()
    )


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key).strip(): str(item).strip()
        for key, item in value.items()
        if str(key).strip() and str(item).strip()
    }


def _required_asset_slots(kind: str) -> tuple[tuple[str, str], ...]:
    return {
        "character": (
            ("character_sheet", "16:9 角色设定总表"),
        ),
        "location": (
            ("master", "总场景"),
            ("interior", "内景"),
            ("exterior", "外景"),
            ("lighting_reference", "灯光参考"),
        ),
        "costume": (
            ("front", "正面"),
            ("back", "背面"),
            ("fabric_detail", "材质细节"),
        ),
        "prop": (
            ("hero", "主视觉"),
            ("scale_reference", "比例参考"),
        ),
        "style": (("moodboard", "风格板"),),
    }.get(kind, ())
