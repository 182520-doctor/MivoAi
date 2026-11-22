import asyncio
from pathlib import Path

from app.contexts.conversations.infrastructure.codex_app_server import (
    CodexAppServerClient,
)
from app.interfaces.agent_media_tools import (
    AgentMediaToolService,
    media_dynamic_tool_specs,
)


class FakeProviders:
    def list_models(self):
        return [
            {
                "id": "image-model",
                "providerId": "comfyui",
                "name": "Image model",
                "capabilities": ["image_generation"],
                "kind": "comfy_workflow",
                "executionMode": "sync",
                "configured": True,
                "parameters": [
                    {
                        "key": "aspectRatio",
                        "default": "1:1",
                    }
                ],
                "references": [
                    {
                        "type": "image",
                        "min": 1,
                        "max": 10,
                    }
                ],
            },
            {
                "id": "text-model",
                "providerId": "codex_local",
                "name": "Text model",
                "capabilities": ["text"],
                "kind": "builtin",
                "executionMode": "sync",
                "configured": True,
                "parameters": [],
                "references": [],
            },
            {
                "id": "audio-model",
                "providerId": "comfyui",
                "name": "Audio separation",
                "capabilities": ["audio_processing"],
                "kind": "comfy_workflow",
                "executionMode": "sync",
                "configured": True,
                "parameters": [],
                "references": [{"type": "audio"}],
            },
        ]


class FakeAssets:
    def list(self, *, limit=50):
        return {
            "assets": [
                {
                    "id": "asset-1",
                    "type": "image",
                    "source": "upload",
                }
            ]
        }


class FakeGeneration:
    async def create(self, command):
        return {"id": "task-1", "status": "running"}

    def get(self, task_id):
        return {
            "id": task_id,
            "status": "succeeded",
            "taskType": "image_generation",
            "modelName": "Image model",
            "resultAssetIds": ["result-1"],
            "resultUrls": ["http://127.0.0.1:8010/api/assets/result-1"],
            "errorMessage": None,
        }

    async def retry_many(self, task_ids):
        return {
            "tasks": [
                {"id": f"retry-{task_id}", "status": "queued"}
                for task_id in task_ids
            ],
            "failures": [],
        }


class FakeMediaProcessing:
    def speech_voices(self):
        return [{"name": "Huihui", "culture": "zh-CN"}]

    def synthesize_speech(self, text, *, voice_name, rate, filename):
        return {"assetId": "tts-1", "type": "audio", "url": "/tts-1"}

    def extract_audio(self, asset_id):
        return {"assetId": "audio-1", "sourceAssetId": asset_id, "type": "audio"}

    def upscale_video(self, asset_id, *, aspect_ratio):
        return {
            "assetId": "video-2",
            "sourceAssetId": asset_id,
            "type": "video",
            "aspectRatio": aspect_ratio,
        }

    def normalize_audio(
        self,
        asset_id,
        *,
        target_lufs,
        true_peak_db,
        loudness_range,
    ):
        return {
            "assetId": "audio-normalized",
            "sourceAssetId": asset_id,
            "type": "audio",
            "targetLufs": target_lufs,
            "truePeakDb": true_peak_db,
            "loudnessRange": loudness_range,
        }

    def transcribe_audio(self, asset_id, *, language):
        return {
            "assetId": "transcript-1",
            "sourceAssetId": asset_id,
            "type": "file",
            "language": language,
            "cues": [
                {
                    "startSeconds": 0,
                    "endSeconds": 1,
                    "text": "测试字幕",
                }
            ],
        }


class FakeDrama:
    def list_projects(self, limit=100):
        return [{"id": "project-1", "title": "Drama"}]

    def production(self, project_id):
        return [{"id": "episode-1", "projectId": project_id, "scenes": []}]

    def series_production(self, project_id):
        return {
            "projectId": project_id,
            "projectTitle": "Test Drama",
            "totals": {
                "episodes": 2,
                "plansComplete": 1,
                "scenes": 2,
                "shots": 4,
                "keyframesReady": 2,
                "videosReady": 1,
                "shotsApproved": 1,
                "episodesRendered": 0,
            },
            "episodes": [],
        }

    def get_project(self, project_id):
        return {
            "id": project_id,
            "title": "Test Drama",
            "format": "9:16",
            "visualStyle": "东方古风",
        }

    def episode_production(self, episode_id):
        return {
            "id": episode_id,
            "projectId": "project-1",
            "title": "第 1 集",
            "scenes": [
                {
                    "id": "scene-1",
                    "shots": [
                        {
                            "id": "shot-1",
                            "title": "铜镜发现",
                            "description": "公主触碰铜镜。",
                            "dialogue": "公主：这是什么？",
                            "durationSeconds": 5,
                            "firstFrameAssetId": None,
                            "lastFrameAssetId": None,
                            "grid9AssetId": None,
                            "storyboardAssetId": None,
                            "videoAssetId": None,
                            "promptOverrides": {
                                "first_frame": "用户保存的首帧提示词",
                            },
                            "entityReferences": [
                                {
                                    "entityId": "entity-1",
                                    "role": "character",
                                }
                            ],
                        }
                    ],
                }
            ],
            "sceneCount": 1,
            "shotCount": 1,
            "planComplete": False,
        }

    def list_entities(self, project_id):
        return [
            {
                "id": "entity-1",
                "projectId": project_id,
                "kind": "character",
                "name": "宋宁公主",
                "description": "宋制公主造型",
                "primaryAssetId": "asset-character",
                "referenceAssetIds": [],
                "assetSlots": {},
                "assetPrompts": {
                    "turnaround_front": "用户保存的资产提示词",
                },
            }
        ]

    def audit_episode(self, episode_id):
        return {
            "episodeId": episode_id,
            "score": 82,
            "readyForAssets": False,
            "issues": [{"code": "episode_plan_locations"}],
        }

    def audit_script(self, project_id):
        return {
            "projectId": project_id,
            "score": 75,
            "readyForReview": False,
            "issues": [{"code": "script_scene_missing"}],
        }

    def audit(self, project_id):
        return {
            "projectId": project_id,
            "score": 90,
            "ready": True,
            "issues": [],
        }

    def roles(self, stage=None):
        return [
            {
                "id": "screenwriter",
                "title": "编剧",
                "stageIds": [stage or "script"],
                "checklist": ["检查故事结构"],
            }
        ]

    def production_control(self, project_id):
        return {
            "project": {"id": project_id},
            "gates": [{"stage": "script", "status": "awaiting_user"}],
        }

    def create_document(
        self,
        project_id,
        *,
        kind,
        title,
        content,
    ):
        return {
            "id": "document-1",
            "projectId": project_id,
            "kind": kind,
            "title": title,
            "content": content,
            "status": "draft",
        }

    def plan_episodes(self, project_id, episodes):
        return [
            {"id": "episode-1", "projectId": project_id, **episodes[0]}
        ]

    def plan_episode_shots(self, episode_id, scenes):
        return {"episodeId": episode_id, "scenes": scenes}

    def plan_assets(self, project_id, entities):
        return [{"id": "entity-1", "projectId": project_id, **entities[0]}]

    def bind_entity_asset(self, entity_id, *, slot, asset_id):
        return {
            "id": entity_id,
            "assetSlots": {slot: asset_id},
        }

    def bind_shot_asset(self, shot_id, *, slot, asset_id):
        return {
            "id": shot_id,
            "slot": slot,
            "assetId": asset_id,
        }

    def update_shot_prompt(self, shot_id, *, slot, prompt):
        return {
            "id": shot_id,
            "promptOverrides": {slot: prompt},
        }

    def update_shot_direction(self, shot_id, *, direction):
        return {
            "id": shot_id,
            "direction": dict(direction),
        }

    def update_entity_prompt(self, entity_id, *, slot, prompt):
        return {
            "id": entity_id,
            "assetPrompts": {slot: prompt},
        }

    def list_asset_candidates(
        self,
        project_id,
        *,
        subject_type=None,
        subject_id=None,
        slot=None,
    ):
        return [
            {
                "id": "candidate-1",
                "projectId": project_id,
                "subjectType": subject_type or "shot",
                "subjectId": subject_id or "shot-1",
                "slot": slot or "first_frame",
                "assetId": "asset-front",
                "status": "selected",
            }
        ]

    def update_asset_candidate_status(self, candidate_id, *, status):
        return {
            "id": candidate_id,
            "assetId": "asset-front",
            "status": status,
        }

    def list_production_runs(
        self,
        project_id,
        *,
        episode_id=None,
        limit=50,
    ):
        return [
            {
                "id": "run-1",
                "projectId": project_id,
                "episodeId": episode_id or "episode-1",
                "status": "awaiting_approval",
            }
        ]

    def create_production_run(
        self,
        project_id,
        *,
        episode_id,
        stage,
        name,
        requires_approval,
        max_parallel,
        items,
        planning=None,
    ):
        return {
            "id": "run-1",
            "projectId": project_id,
            "episodeId": episode_id,
            "stage": stage,
            "name": name,
            "status": (
                "awaiting_approval" if requires_approval else "draft"
            ),
            "maxParallel": max_parallel,
            "planning": planning or {},
            "items": items,
        }

    def get_production_run(self, run_id):
        return {"id": run_id, "status": "partial"}

    def start_production_run(self, run_id, *, approved_by):
        return {
            "id": run_id,
            "status": "queued",
            "approvedBy": approved_by,
        }

    def retry_failed_production_run(self, run_id, *, approved_by):
        return {
            "id": run_id,
            "status": "queued",
            "approvedBy": approved_by,
        }

    def cancel_production_run(self, run_id):
        return {"id": run_id, "status": "canceled"}

    def export_manifests(self, episode_id):
        return [
            {
                "id": "manifest-1",
                "episodeId": episode_id,
                "manifest": {"schemaVersion": 1},
            }
        ]

    def record_review(self, project_id, **changes):
        return {
            "id": "review-1",
            "projectId": project_id,
            **changes,
        }

    def update_shot(self, shot_id, **changes):
        mapping = {
            "audio_asset_id": "audioAssetId",
            "video_asset_id": "videoAssetId",
            "first_frame_asset_id": "firstFrameAssetId",
            "last_frame_asset_id": "lastFrameAssetId",
        }
        return {
            "id": shot_id,
            **{
                mapping.get(key, key): value
                for key, value in changes.items()
                if value is not None
            },
        }

    def update_shot_status(
        self,
        shot_id,
        *,
        status,
        reviewer="user",
        note="",
    ):
        return {
            "id": shot_id,
            "status": status,
            "reviewer": reviewer,
            "note": note,
        }

    def shot_status_history(self, shot_id, *, limit=50):
        return [
            {
                "id": "status-event-1",
                "shotId": shot_id,
                "fromStatus": "clip_ready",
                "toStatus": "approved",
                "reviewer": "user",
                "note": "通过",
            }
        ]

    async def render_episode(
        self,
        episode_id,
        *,
        transition,
        transition_duration,
        strict_approvals=True,
    ):
        return {
            "id": episode_id,
            "exportAssetId": "export-1",
            "transition": transition,
            "transitionDuration": transition_duration,
            "strictApprovals": strict_approvals,
        }


def test_media_dynamic_tool_specs_cover_discovery_and_execution() -> None:
    names = {spec["name"] for spec in media_dynamic_tool_specs()}

    assert names == {
        "zaojing_discover_media_models",
        "zaojing_list_media_assets",
        "zaojing_generate_media",
        "zaojing_get_media_task",
        "zaojing_retry_media_tasks",
        "zaojing_get_shared_context",
        "zaojing_list_speech_voices",
        "zaojing_synthesize_speech",
        "zaojing_process_media",
        "zaojing_list_drama_projects",
        "zaojing_get_drama_production",
        "zaojing_get_drama_series",
        "zaojing_get_drama_episode",
        "zaojing_audit_drama_episode",
        "zaojing_audit_drama_script",
        "zaojing_get_drama_roles",
        "zaojing_get_drama_control_room",
        "zaojing_save_drama_draft",
        "zaojing_plan_drama_episodes",
        "zaojing_plan_drama_shots",
        "zaojing_plan_drama_assets",
        "zaojing_bind_drama_asset",
        "zaojing_update_drama_shot_prompt",
        "zaojing_update_drama_shot_direction",
        "zaojing_update_drama_entity_prompt",
        "zaojing_set_drama_shot_status",
        "zaojing_get_drama_shot_history",
        "zaojing_list_drama_asset_candidates",
        "zaojing_update_drama_asset_candidate",
        "zaojing_list_drama_production_runs",
        "zaojing_create_drama_production_run",
        "zaojing_plan_drama_production_run",
        "zaojing_get_drama_production_run",
        "zaojing_start_drama_production_run",
        "zaojing_retry_drama_production_failures",
        "zaojing_cancel_drama_production_run",
        "zaojing_review_drama_stage",
        "zaojing_audit_drama_project",
        "zaojing_render_episode",
        "zaojing_list_drama_export_manifests",
    }


def test_agent_media_tool_discovers_enabled_models() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
    )

    result = asyncio.run(
        service.handle(
            "zaojing_discover_media_models",
            {"capability": "image_generation"},
        )
    )

    assert result["success"] is True
    assert result["data"]["models"][0]["id"] == "image-model"
    assert len(result["data"]["models"]) == 1


def test_agent_media_tool_discovers_audio_processing_model() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
    )

    result = asyncio.run(
        service.handle(
            "zaojing_discover_media_models",
            {"capability": "audio_processing"},
        )
    )

    assert result["success"] is True
    assert result["data"]["models"][0]["id"] == "audio-model"


def test_agent_discovers_image_processing_utility_models() -> None:
    class UtilityProviders(FakeProviders):
        def list_models(self):
            models = super().list_models()
            utility = {
                **models[0],
                "id": "image-upscale",
                "name": "图片放大与细节增强",
                "capabilities": ["image_processing"],
            }
            return [utility, *models]

    service = AgentMediaToolService(
        UtilityProviders(),
        FakeGeneration(),
        FakeAssets(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_discover_media_models",
            {"capability": "image_processing"},
        )
    )

    assert result["success"] is True
    assert [item["id"] for item in result["data"]["models"]] == [
        "image-upscale"
    ]


def test_agent_generation_returns_text_and_result_url_without_remote_image() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
    )

    result = asyncio.run(
        service.handle(
            "zaojing_generate_media",
            {
                "providerId": "comfyui",
                "modelId": "image-model",
                "taskType": "image_generation",
                "prompt": "test",
                "parameters": {"aspectRatio": "1:1"},
                "waitSeconds": 0,
            },
        )
    )

    assert result["success"] is True
    assert result["contentItems"][0]["type"] == "inputText"
    assert all(
        item["type"] != "inputImage"
        for item in result["contentItems"]
    )
    assert result["task"]["resultAssetIds"] == ["result-1"]


def test_agent_retries_media_tasks_in_batch() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_retry_media_tasks",
            {"taskIds": ["failed-1", "failed-2"]},
        )
    )

    assert result["success"] is True
    assert [task["id"] for task in result["data"]["tasks"]] == [
        "retry-failed-1",
        "retry-failed-2",
    ]


def test_agent_reads_shared_playbooks(tmp_path) -> None:
    playbook = tmp_path / "playbooks" / "multimodal.md"
    playbook.parent.mkdir()
    playbook.write_text("# Playbook", encoding="utf-8")
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        tmp_path,
    )

    listing = asyncio.run(
        service.handle("zaojing_get_shared_context", {})
    )
    content = asyncio.run(
        service.handle(
            "zaojing_get_shared_context",
            {"path": "playbooks/multimodal.md"},
        )
    )

    assert listing["data"]["files"] == ["playbooks/multimodal.md"]
    assert content["data"]["content"] == "# Playbook"


def test_agent_generates_speech_and_binds_shot() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_synthesize_speech",
            {
                "text": "你好",
                "voiceName": "Huihui",
                "shotId": "shot-1",
            },
        )
    )
    assert result["success"] is True
    assert result["data"]["assetId"] == "tts-1"
    assert result["data"]["shot"]["audioAssetId"] == "tts-1"


def test_agent_renders_episode_with_crossfade() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_render_episode",
            {
                "episodeId": "episode-1",
                "transition": "crossfade",
                "transitionDuration": 0.5,
            },
        )
    )
    assert result["success"] is True
    assert result["data"]["exportAssetId"] == "export-1"
    assert result["data"]["transitionDuration"] == 0.5


def test_agent_runs_drama_audit() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_audit_drama_project",
            {"projectId": "project-1"},
        )
    )
    assert result["success"] is True
    assert result["data"]["audit"]["score"] == 90


def test_agent_reads_one_drama_episode() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_get_drama_episode",
            {"episodeId": "episode-1"},
        )
    )
    assert result["success"] is True
    assert result["data"]["episode"]["id"] == "episode-1"
    assert result["data"]["episode"]["planComplete"] is False


def test_agent_reads_multi_episode_production_overview() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_get_drama_series",
            {"projectId": "project-1"},
        )
    )

    assert result["success"] is True
    assert result["data"]["series"]["totals"]["episodes"] == 2
    assert result["data"]["series"]["totals"]["videosReady"] == 1


def test_agent_audits_one_drama_episode() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_audit_drama_episode",
            {"episodeId": "episode-1"},
        )
    )
    assert result["success"] is True
    assert result["data"]["audit"]["score"] == 82
    assert result["data"]["audit"]["readyForAssets"] is False


def test_agent_audits_drama_script() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_audit_drama_script",
            {"projectId": "project-1"},
        )
    )
    assert result["success"] is True
    assert result["data"]["audit"]["score"] == 75
    assert result["data"]["audit"]["readyForReview"] is False


def test_agent_reads_drama_roles_and_records_review() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    roles = asyncio.run(
        service.handle(
            "zaojing_get_drama_roles",
            {"stage": "script"},
        )
    )
    review = asyncio.run(
        service.handle(
            "zaojing_review_drama_stage",
            {
                "projectId": "project-1",
                "stage": "script",
                "roleId": "screenwriter",
                "status": "passed",
                "score": 92,
                "checklist": [
                    {
                        "key": "hook",
                        "label": "结尾钩子",
                        "passed": True,
                    }
                ],
                "feedback": "结构可进入分集拆解。",
            },
        )
    )

    assert roles["data"]["roles"][0]["title"] == "编剧"
    assert review["data"]["review"]["reviewer"] == "agent"
    assert review["data"]["review"]["score"] == 92


def test_agent_binds_drama_asset_to_semantic_slot() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    entity = asyncio.run(
        service.handle(
            "zaojing_bind_drama_asset",
            {
                "targetType": "entity",
                "targetId": "entity-1",
                "slot": "turnaround_front",
                "assetId": "asset-front",
            },
        )
    )
    shot = asyncio.run(
        service.handle(
            "zaojing_bind_drama_asset",
            {
                "targetType": "shot",
                "targetId": "shot-1",
                "slot": "grid9",
                "assetId": "asset-grid",
            },
        )
    )

    assert (
        entity["data"]["bound"]["assetSlots"]["turnaround_front"]
        == "asset-front"
    )
    assert shot["data"]["bound"]["slot"] == "grid9"
    assert shot["data"]["bound"]["assetId"] == "asset-grid"


def test_agent_manages_drama_asset_candidates() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    listing = asyncio.run(
        service.handle(
            "zaojing_list_drama_asset_candidates",
            {
                "projectId": "project-1",
                "subjectType": "shot",
                "subjectId": "shot-1",
                "slot": "first_frame",
            },
        )
    )
    updated = asyncio.run(
        service.handle(
            "zaojing_update_drama_asset_candidate",
            {"candidateId": "candidate-1", "status": "rejected"},
        )
    )

    assert listing["success"] is True
    assert listing["data"]["candidates"][0]["id"] == "candidate-1"
    assert updated["data"]["candidate"]["status"] == "rejected"


def test_agent_creates_and_starts_drama_production_run() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    created = asyncio.run(
        service.handle(
            "zaojing_create_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "keyframes",
                "name": "首帧批处理",
                "requiresApproval": True,
                "maxParallel": 1,
                "items": [
                    {
                        "targetType": "shot",
                        "targetId": "shot-1",
                        "slot": "first_frame",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "首帧",
                        },
                    }
                ],
            },
        )
    )
    started = asyncio.run(
        service.handle(
            "zaojing_start_drama_production_run",
            {"runId": "run-1", "approvedBy": "local-user"},
        )
    )

    assert created["data"]["run"]["status"] == "awaiting_approval"
    assert started["data"]["run"]["status"] == "queued"
    assert started["data"]["run"]["approvedBy"] == "local-user"


def test_agent_plans_drama_run_from_episode_and_assets() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "keyframes",
                "providerId": "comfyui",
                "modelId": "image-model",
                "slots": ["first_frame"],
            },
        )
    )

    assert result["success"] is True
    run = result["data"]["run"]
    assert len(run["items"]) == 1
    item = run["items"][0]
    assert item["targetId"] == "shot-1"
    assert item["request"]["images"] == ["asset-character"]
    assert item["request"]["parameters"]["aspectRatio"] == "9:16"
    assert item["request"]["prompt"] == "用户保存的首帧提示词"
    assert result["data"]["skipped"] == []


def test_agent_shot_prompts_include_scene_contract_context() -> None:
    class ContractProviders(FakeProviders):
        def list_models(self):
            models = super().list_models()
            return [
                *models,
                {
                    **models[0],
                    "id": "video-model",
                    "name": "Video model",
                    "capabilities": ["video_generation"],
                    "parameters": [{"key": "duration", "default": 5}],
                },
            ]

    class ContractDrama(FakeDrama):
        def episode_production(self, episode_id):
            episode = super().episode_production(episode_id)
            episode["scenes"][0]["sceneNumber"] = 1
            episode["scenes"][0]["shots"][0]["direction"] = {
                "shotSize": "中近景",
                "cameraAngle": "平视略低",
                "cameraMovement": "极慢推近",
                "blocking": "人物从窗边转向铜镜",
                "performanceAction": "呼吸收紧后伸手",
                "lighting": "窗侧月光与暖烛补光",
            }
            episode["plan"] = {
                "sceneContracts": [
                    {
                        "sceneNumber": 1,
                        "valueIn": "安全",
                        "valueOut": "暴露风险",
                        "characterObjectives": ["宋宁：确认画像来源"],
                        "obstacle": "画像中的线索互相矛盾",
                        "tactics": ["试探", "逼近观察"],
                        "beats": ["发现", "迟疑", "触碰"],
                        "turn": "画像衣饰突然变化",
                        "subtext": "她害怕自己遗忘了另一个人",
                        "performanceNotes": "呼吸收紧，手指触碰前停顿",
                        "visualStrategy": "铜镜反射与真实空间形成错位",
                        "soundNotes": "竹影声在触碰前突然停止",
                    }
                ]
            }
            return episode

    service = AgentMediaToolService(
        ContractProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=ContractDrama(),
    )
    keyframe = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "keyframes",
                "providerId": "comfyui",
                "modelId": "image-model",
                "slots": ["last_frame"],
            },
        )
    )
    video = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "clips",
                "providerId": "comfyui",
                "modelId": "video-model",
                "slots": ["video"],
            },
        )
    )

    assert keyframe["success"] is True
    assert video["success"] is True
    keyframe_prompt = keyframe["data"]["run"]["items"][0]["request"]["prompt"]
    video_prompt = video["data"]["run"]["items"][0]["request"]["prompt"]
    assert "从“安全”转向“暴露风险”" in keyframe_prompt
    assert "声台形表：呼吸收紧" in keyframe_prompt
    assert "景别：中近景" in keyframe_prompt
    assert "镜头运动：极慢推近" in keyframe_prompt
    assert "关键转折：画像衣饰突然变化" in video_prompt
    assert "声音策略：竹影声在触碰前突然停止" in video_prompt


def test_agent_plan_uses_saved_entity_prompt() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "assets",
                "providerId": "comfyui",
                "modelId": "image-model",
                "slots": ["turnaround_front"],
            },
        )
    )

    assert result["success"] is True
    item = result["data"]["run"]["items"][0]
    assert item["request"]["prompt"] == "用户保存的资产提示词"
    assert item["request"]["images"] == ["asset-character"]


def test_agent_default_character_asset_is_one_16x9_sheet() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "assets",
                "providerId": "comfyui",
                "modelId": "image-model",
            },
        )
    )

    assert result["success"] is True
    run = result["data"]["run"]
    assert [item["slot"] for item in run["items"]] == ["character_sheet"]
    item = run["items"][0]
    assert item["title"] == "宋宁公主 · 16:9 角色设定总表"
    assert item["request"]["parameters"]["aspectRatio"] == "16:9"
    prompt = item["request"]["prompt"]
    assert "单张 16:9" in prompt
    assert "全身正面、正侧面和背面" in prompt
    assert "不是六张独立图片" in prompt
    assert result["data"]["skipped"] == []


def test_agent_assets_plan_bootstraps_primary_before_detail_views() -> None:
    class TextToImageProviders(FakeProviders):
        def list_models(self):
            models = super().list_models()
            image = dict(models[0])
            image["references"] = [
                {"type": "image", "min": 0, "max": 0}
            ]
            return [image, *models[1:]]

    class UnseededDrama(FakeDrama):
        def list_entities(self, project_id):
            entities = super().list_entities(project_id)
            return [
                {
                    **entities[0],
                    "primaryAssetId": None,
                    "referenceAssetIds": [],
                    "assetSlots": {},
                }
            ]

    service = AgentMediaToolService(
        TextToImageProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=UnseededDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_plan_drama_production_run",
            {
                "projectId": "project-1",
                "episodeId": "episode-1",
                "stage": "assets",
                "providerId": "comfyui",
                "modelId": "image-model",
            },
        )
    )

    assert result["success"] is True
    run = result["data"]["run"]
    assert [item["slot"] for item in run["items"]] == ["primary"]
    assert len(result["data"]["skipped"]) == 1
    assert all(
        "先生成 primary" in item["reason"]
        for item in result["data"]["skipped"]
    )
    assert run["planning"]["source"] == "agent_plan"
    assert len(run["planning"]["skipped"]) == 1


def test_agent_lists_drama_export_manifests() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_list_drama_export_manifests",
            {"episodeId": "episode-1"},
        )
    )

    assert result["success"] is True
    assert result["data"]["manifests"][0]["id"] == "manifest-1"


def test_agent_saves_durable_shot_prompt() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_update_drama_shot_prompt",
            {
                "shotId": "shot-1",
                "slot": "video",
                "prompt": "持久视频提示词",
            },
        )
    )

    assert result["success"] is True
    assert (
        result["data"]["shot"]["promptOverrides"]["video"]
        == "持久视频提示词"
    )


def test_agent_saves_structured_shot_direction() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_update_drama_shot_direction",
            {
                "shotId": "shot-1",
                "direction": {
                    "shotSize": "中近景",
                    "cameraAngle": "平视略低",
                    "cameraMovement": "极慢推近",
                    "blocking": "人物从窗边转向铜镜",
                    "performanceAction": "呼吸收紧后伸手",
                    "lighting": "窗侧月光与暖烛补光",
                },
            },
        )
    )

    assert result["success"] is True
    assert result["data"]["shot"]["direction"]["shotSize"] == "中近景"
    assert result["data"]["shot"]["direction"]["cameraMovement"] == "极慢推近"


def test_agent_saves_durable_entity_prompt() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_update_drama_entity_prompt",
            {
                "entityId": "entity-1",
                "slot": "turnaround_front",
                "prompt": "统一角色正面造型提示词",
            },
        )
    )

    assert result["success"] is True
    assert (
        result["data"]["entity"]["assetPrompts"]["turnaround_front"]
        == "统一角色正面造型提示词"
    )


def test_agent_approves_drama_shot() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_set_drama_shot_status",
            {"shotId": "shot-1", "status": "approved"},
        )
    )

    assert result["success"] is True
    assert result["data"]["shot"]["status"] == "approved"
    assert result["data"]["shot"]["reviewer"] == "agent"


def test_agent_reads_drama_shot_status_history() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_get_drama_shot_history",
            {"shotId": "shot-1"},
        )
    )

    assert result["success"] is True
    assert result["data"]["events"][0]["toStatus"] == "approved"


def test_agent_upscales_video_and_attaches_shot() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_process_media",
            {
                "action": "upscale_video",
                "videoAssetId": "video-1",
                "aspectRatio": "9:16",
                "shotId": "shot-1",
            },
        )
    )
    assert result["success"] is True
    assert result["data"]["assetId"] == "video-2"
    assert result["data"]["shot"]["videoAssetId"] == "video-2"


def test_agent_normalizes_audio_and_attaches_shot() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_process_media",
            {
                "action": "normalize_audio",
                "assetId": "audio-1",
                "targetLufs": -16,
                "truePeakDb": -1.5,
                "loudnessRange": 11,
                "shotId": "shot-1",
            },
        )
    )
    assert result["success"] is True
    assert result["data"]["assetId"] == "audio-normalized"
    assert result["data"]["shot"]["audioAssetId"] == "audio-normalized"


def test_agent_transcribes_audio_to_subtitle_cues() -> None:
    service = AgentMediaToolService(
        FakeProviders(),
        FakeGeneration(),
        FakeAssets(),
        media_processing=FakeMediaProcessing(),
        drama=FakeDrama(),
    )
    result = asyncio.run(
        service.handle(
            "zaojing_process_media",
            {
                "action": "transcribe_audio",
                "assetId": "audio-1",
                "language": "zh",
            },
        )
    )
    assert result["success"] is True
    assert result["data"]["assetId"] == "transcript-1"
    assert result["data"]["cues"][0]["text"] == "测试字幕"


def test_codex_dynamic_tool_call_returns_client_result() -> None:
    sent = []

    async def handler(tool, arguments):
        return {
            "success": True,
            "contentItems": [
                {
                    "type": "inputText",
                    "text": f"{tool}:{arguments['value']}",
                }
            ],
        }

    client = CodexAppServerClient(
        binary=Path("codex.exe"),
        workspace=Path("."),
        protocol_log=Path("protocol.log"),
        protocol_logging_enabled=False,
        dynamic_tools=media_dynamic_tool_specs(),
        dynamic_tool_handler=handler,
    )

    async def fake_send(payload):
        sent.append(payload)

    client._send = fake_send  # type: ignore[method-assign]
    asyncio.run(
        client._handle_server_request(
            {
                "id": 7,
                "method": "item/tool/call",
                "params": {
                    "tool": "test_tool",
                    "arguments": {"value": "ok"},
                    "callId": "call-1",
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                },
            }
        )
    )

    assert sent == [
        {
            "id": 7,
            "result": {
                "success": True,
                "contentItems": [
                    {"type": "inputText", "text": "test_tool:ok"}
                ],
            },
        }
    ]


def test_dynamic_tool_lifecycle_is_exposed_to_chat_ui() -> None:
    started = CodexAppServerClient._normalize_turn_event(
        {
            "method": "item/started",
            "params": {
                "turnId": "turn-1",
                "item": {
                    "id": "call-1",
                    "type": "dynamicToolCall",
                    "tool": "zaojing_discover_media_models",
                    "arguments": {},
                    "status": "inProgress",
                },
            },
        },
        "turn-1",
    )
    completed = CodexAppServerClient._normalize_turn_event(
        {
            "method": "item/completed",
            "params": {
                "turnId": "turn-1",
                "item": {
                    "id": "call-1",
                    "type": "dynamicToolCall",
                    "tool": "zaojing_discover_media_models",
                    "arguments": {},
                    "status": "completed",
                    "success": True,
                    "contentItems": [
                        {"type": "inputText", "text": "{\"models\": []}"}
                    ],
                },
            },
        },
        "turn-1",
    )

    assert started["type"] == "tool_started"
    assert started["toolCallId"] == "call-1"
    assert completed["type"] == "tool_completed"
    assert completed["success"] is True
