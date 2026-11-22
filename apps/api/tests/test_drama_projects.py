import time
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.shared.config import Settings
from tests.fakes import FakeCodexClient


class FakeTimelineRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

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
    ) -> str:
        self.calls.append(
            {
                "videoAssetIds": video_asset_ids,
                "aspectRatio": aspect_ratio,
                "filename": filename,
                "subtitleCues": subtitle_cues,
                "audioAssetIds": audio_asset_ids,
                "subtitleStyle": subtitle_style,
                "transition": transition,
                "transitionDuration": transition_duration,
                "musicAssetId": music_asset_id,
                "musicVolumeDb": music_volume_db,
                "ambienceAssetId": ambience_asset_id,
                "ambienceVolumeDb": ambience_volume_db,
                "ducking": ducking,
                "soundEffects": sound_effects,
            }
        )
        return "episode-export"


class FakeProductionMedia:
    def __init__(self, asset_ids: list[str]) -> None:
        self._asset_ids = list(asset_ids)
        self._tasks: dict[str, dict[str, object]] = {}
        self._submitted = 0
        self._fail_once_prompts: set[str] = set()
        self.requests: list[dict[str, object]] = []

    async def submit(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        self._submitted += 1
        task_id = f"run-task-{self._submitted}"
        prompt = str(request.get("prompt") or "")
        should_fail = "FAIL" in prompt and prompt not in self._fail_once_prompts
        if should_fail:
            self._fail_once_prompts.add(prompt)
        asset_id = (
            self._asset_ids[min(self._submitted - 1, len(self._asset_ids) - 1)]
            if self._asset_ids
            else None
        )
        self._tasks[task_id] = {
            "id": task_id,
            "status": "failed" if should_fail else "succeeded",
            "resultAssetIds": [] if should_fail else [asset_id],
            "errorMessage": "模拟失败" if should_fail else None,
        }
        return {"id": task_id, "status": "queued"}

    def get(self, task_id: str) -> dict[str, object]:
        return self._tasks[task_id]


class RestartableProductionMedia(FakeProductionMedia):
    def __init__(self, asset_id: str) -> None:
        super().__init__([asset_id])
        self._restart_asset_id = asset_id

    async def submit(self, request: dict[str, object]) -> dict[str, object]:
        self._submitted += 1
        task_id = f"restart-task-{self._submitted}"
        self._tasks[task_id] = {
            "id": task_id,
            "status": "running",
            "resultAssetIds": [],
            "errorMessage": None,
        }
        return {"id": task_id, "status": "running"}

    def complete_all(self) -> None:
        for task in self._tasks.values():
            task["status"] = "succeeded"
            task["resultAssetIds"] = [self._restart_asset_id]


def _wait_for_run(client, run_id: str, statuses: set[str]):
    for _ in range(100):
        response = client.get(
            f"/api/drama/projects/production-runs/{run_id}"
        )
        assert response.status_code == 200
        run = response.json()
        if run["status"] in statuses:
            return run
        time.sleep(0.02)
    raise AssertionError(f"production run did not reach {statuses}: {run}")


def _complete_episode_plan(
    client,
    episode_id: str,
    *,
    location: str = "制作运行",
) -> None:
    response = client.put(
        f"/api/drama/projects/episodes/{episode_id}/plan",
        json={
            "timeScope": "当夜连续发生",
            "locations": [location],
            "interiorExterior": ["内景"],
            "characters": ["测试角色"],
            "scenes": ["制作运行·主场景"],
            "storyBeats": ["建立冲突", "推进动作", "留下钩子"],
            "visualRequirements": ["光源方向连续"],
            "dialogueRequirements": ["明确说话人"],
            "continuityRisks": ["保持角色服装一致"],
        },
    )
    assert response.status_code == 200


def test_drama_project_lifecycle_and_workspace(tmp_path) -> None:
    database_path = tmp_path / "drama.db"
    drama_workspace = tmp_path / "drama-workspace"
    settings = replace(
        Settings.from_env(),
        database_path=database_path,
        drama_workspace=drama_workspace,
    )
    app = create_app(
        FakeCodexClient(),
        settings=settings,
        database_path=database_path,
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/drama/projects",
            json={
                "idea": "一位宋朝公主发现画师记录了她的另一重身份",
                "format": "9:16",
                "visualStyle": "东方古风",
            },
        )
        assert created.status_code == 200
        project = created.json()
        project_id = project["id"]
        workspace = Path(project["workspace"])
        assert workspace.is_dir()
        assert (workspace / "shots").is_dir()
        assert (workspace / "assets").is_dir()

        listing = client.get("/api/drama/projects")
        assert listing.status_code == 200
        assert listing.json()[0]["id"] == project_id

        documents = client.get(
            f"/api/drama/projects/{project_id}/documents"
        ).json()
        assert documents[0]["kind"] == "brief"
        assert documents[0]["version"] == 1

        bible = client.post(
            f"/api/drama/projects/{project_id}/documents",
            json={
                "kind": "story_bible",
                "title": "故事圣经",
                "content": "公主与画师的连续性规则。",
            },
        )
        assert bible.status_code == 200
        bible_id = bible.json()["id"]
        updated_bible = client.patch(
            f"/api/drama/projects/documents/{bible_id}",
            json={
                "title": "故事圣经 v1",
                "content": "角色、服装、场景与道具规则。",
            },
        )
        assert updated_bible.status_code == 200
        approved = client.post(
            f"/api/drama/projects/documents/{bible_id}/approve"
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        rejected_edit = client.patch(
            f"/api/drama/projects/documents/{bible_id}",
            json={"content": "不应修改"},
        )
        assert rejected_edit.status_code == 400

        episode = client.post(
            f"/api/drama/projects/{project_id}/episodes",
            json={"title": "第 1 集", "synopsis": "镜中初见"},
        )
        assert episode.status_code == 200
        episode_id = episode.json()["id"]
        assert episode.json()["episodeNumber"] == 1

        scene = client.post(
            f"/api/drama/projects/episodes/{episode_id}/scenes",
            json={
                "heading": "内景｜公主寝宫｜夜",
                "summary": "公主发现陌生画像。",
            },
        )
        assert scene.status_code == 200
        scene_id = scene.json()["id"]
        assert scene.json()["sceneNumber"] == 1

        shot = client.post(
            f"/api/drama/projects/scenes/{scene_id}/shots",
            json={
                "title": "铜镜前的发现",
                "description": "公主触摸铜镜上的朱砂印记。",
                "dialogue": "宋宁公主：这幅画为何有我的记忆？",
                "durationSeconds": 5,
            },
        )
        assert shot.status_code == 200
        shot_id = shot.json()["id"]
        assert shot.json()["shotNumber"] == 1
        updated_shot = client.patch(
            f"/api/drama/projects/shots/{shot_id}",
            json={"status": "keyframe_ready"},
        )
        assert updated_shot.status_code == 200
        assert updated_shot.json()["status"] == "keyframe_ready"
        attached_frame = client.patch(
            f"/api/drama/projects/shots/{shot_id}",
            json={"firstFrameAssetId": "asset-first-frame"},
        )
        assert attached_frame.status_code == 200
        assert (
            attached_frame.json()["firstFrameAssetId"]
            == "asset-first-frame"
        )
        attached_audio = client.patch(
            f"/api/drama/projects/shots/{shot_id}",
            json={"audioAssetId": "asset-shot-audio"},
        )
        assert attached_audio.status_code == 200
        assert attached_audio.json()["audioAssetId"] == "asset-shot-audio"

        character = client.post(
            f"/api/drama/projects/{project_id}/entities",
            json={
                "kind": "character",
                "name": "宋宁公主",
                "description": "宋朝公主，服装以月白、深青为主。",
            },
        )
        assert character.status_code == 200
        character_id = character.json()["id"]
        location = client.post(
            f"/api/drama/projects/{project_id}/entities",
            json={
                "kind": "location",
                "name": "公主寝宫",
                "description": "木格窗、青瓷瓶、香炉与竹影。",
            },
        )
        assert location.status_code == 200
        location_id = location.json()["id"]
        locked_character = client.patch(
            f"/api/drama/projects/entities/{character_id}",
            json={
                "name": "宋宁公主",
                "description": "已锁定的角色定妆。",
                "status": "locked",
                "primaryAssetId": "asset-character",
                "voiceName": "Microsoft Huihui Desktop",
                "voiceRate": -1,
            },
        )
        assert locked_character.status_code == 200
        assert locked_character.json()["status"] == "locked"
        assert (
            locked_character.json()["voiceName"]
            == "Microsoft Huihui Desktop"
        )
        assert locked_character.json()["voiceRate"] == -1
        locked_location = client.patch(
            f"/api/drama/projects/entities/{location_id}",
            json={
                "name": "公主寝宫",
                "description": "已锁定的场景概念。",
                "status": "locked",
                "primaryAssetId": "asset-location",
            },
        )
        assert locked_location.status_code == 200
        references = client.put(
            f"/api/drama/projects/shots/{shot_id}/references",
            json={
                "references": [
                    {"entityId": character_id, "role": "character"},
                    {"entityId": location_id, "role": "location"},
                ]
            },
        )
        assert references.status_code == 200
        assert len(references.json()["references"]) == 2

        production = client.get(
            f"/api/drama/projects/{project_id}/production"
        )
        assert production.status_code == 200
        assert production.json()[0]["scenes"][0]["shots"][0]["id"] == shot_id
        assert (
            len(
                production.json()[0]["scenes"][0]["shots"][0][
                    "entityReferences"
                ]
            )
            == 2
        )
        audit = client.get(f"/api/drama/projects/{project_id}/audit")
        assert audit.status_code == 200
        assert audit.json()["shotCount"] == 1
        assert audit.json()["ready"] is False
        assert any(
            issue["code"] == "shot_video_missing"
            for issue in audit.json()["issues"]
        )

        updated = client.patch(
            f"/api/drama/projects/{project_id}",
            json={"activeStage": "script", "status": "in_progress"},
        )
        assert updated.status_code == 200
        assert updated.json()["activeStage"] == "script"
        assert updated.json()["status"] == "in_progress"

    restarted = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(restarted) as client:
        projects = client.get("/api/drama/projects").json()
        assert projects[0]["id"] == project_id
        assert projects[0]["activeStage"] == "script"
        documents = client.get(
            f"/api/drama/projects/{project_id}/documents"
        ).json()
        assert any(
            document["kind"] == "story_bible"
            and document["status"] == "approved"
            for document in documents
        )
        production = client.get(
            f"/api/drama/projects/{project_id}/production"
        ).json()
        assert production[0]["scenes"][0]["shots"][0]["status"] == "keyframe_ready"
        assert (
            production[0]["scenes"][0]["shots"][0]["firstFrameAssetId"]
            == "asset-first-frame"
        )
        assert (
            production[0]["scenes"][0]["shots"][0]["audioAssetId"]
            == "asset-shot-audio"
        )
        entities = client.get(
            f"/api/drama/projects/{project_id}/entities"
        ).json()
        assert {entity["kind"] for entity in entities} == {
            "character",
            "location",
        }
        assert all(entity["status"] == "locked" for entity in entities)
        character = next(
            entity
            for entity in entities
            if entity["kind"] == "character"
        )
        assert character["voiceName"] == "Microsoft Huihui Desktop"
        assert character["voiceRate"] == -1


def test_drama_project_rejects_unknown_stage(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "drama.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "测试短剧"},
        ).json()
        response = client.patch(
            f"/api/drama/projects/{project['id']}",
            json={"activeStage": "unknown"},
        )
    assert response.status_code == 400


def test_episode_audit_detects_scene_and_dialogue_conflicts(
    tmp_path,
) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "audit.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "分集审核冲突测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        client.put(
            f"/api/drama/projects/episodes/{episode['id']}/plan",
            json={
                "timeScope": "当夜",
                "locations": ["公主寝宫", "宫墙"],
                "interiorExterior": ["内景", "外景"],
                "characters": ["宋宁公主"],
                "scenes": ["寝宫发现", "宫墙追逐"],
                "storyBeats": ["发现秘密", "追出宫墙"],
                "visualRequirements": ["铜镜反光连续"],
                "dialogueRequirements": ["对白注明说话人"],
            },
        )
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜公主寝宫｜夜"},
        ).json()
        client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "发现",
                "description": "看镜子",
                "dialogue": "陌生画师：画中的人是谁？",
                "durationSeconds": 20,
            },
        )
        client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "画外回应",
                "description": "宋宁公主听见画外回应并停下动作。",
                "dialogue": "宋宁公主（画外）：这不可能。",
            },
        )
        audit = client.get(
            f"/api/drama/projects/episodes/{episode['id']}/audit"
        ).json()

    codes = {issue["code"] for issue in audit["issues"]}
    assert "episode_plan_scene_count_mismatch" in codes
    assert "episode_plan_location_not_found" in codes
    assert "shot_description_too_short" in codes
    assert "shot_duration_long" in codes
    assert "shot_dialogue_speaker_unknown" in codes
    assert audit["scenePlanMismatchCount"] >= 2
    assert audit["dialogueSpeakerIssueCount"] == 1


def test_shot_references_reject_entities_from_another_project(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "drama.db")
    with TestClient(app) as client:
        first = client.post(
            "/api/drama/projects",
            json={"idea": "项目一"},
        ).json()
        second = client.post(
            "/api/drama/projects",
            json={"idea": "项目二"},
        ).json()
        entity = client.post(
            f"/api/drama/projects/{second['id']}/entities",
            json={"kind": "character", "name": "其他项目角色"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{first['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜测试｜日"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "测试镜头"},
        ).json()
        response = client.put(
            f"/api/drama/projects/shots/{shot['id']}/references",
            json={
                "references": [
                    {"entityId": entity["id"], "role": "character"},
                ]
            },
        )
    assert response.status_code == 400


def test_drama_production_control_roles_plan_and_user_gate(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "drama.db")
    with TestClient(app) as client:
        roles = client.get("/api/drama/projects/roles?stage=script")
        assert roles.status_code == 200
        assert {role["id"] for role in roles.json()} == {
            "screenwriter",
            "director",
        }

        project = client.post(
            "/api/drama/projects",
            json={"idea": "公主发现画师的秘密"},
        ).json()
        project_id = project["id"]
        client.patch(
            f"/api/drama/projects/{project_id}",
            json={"activeStage": "script", "status": "in_progress"},
        )
        episode = client.post(
            f"/api/drama/projects/{project_id}/episodes",
            json={"title": "第 1 集", "synopsis": "画像中的记忆"},
        ).json()
        plan = client.put(
            f"/api/drama/projects/episodes/{episode['id']}/plan",
            json={
                "timeScope": "同一夜，戌时到卯时",
                "locations": ["公主寝宫", "宫墙"],
                "interiorExterior": ["内景", "外景"],
                "characters": ["宋宁公主", "画师"],
                "scenes": ["镜中发现画像", "宫墙追赶"],
                "storyBeats": ["发现秘密", "追查身份", "留下钩子"],
                "visualRequirements": ["铜镜反光连续"],
                "dialogueRequirements": ["对白标注说话人"],
                "continuityRisks": ["画像出现时间"],
            },
        )
        assert plan.status_code == 200
        assert plan.json()["plan"]["storyBeats"][1] == "追查身份"
        episode_scoped = client.get(
            f"/api/drama/projects/episodes/{episode['id']}/production"
        )
        assert episode_scoped.status_code == 200
        assert episode_scoped.json()["id"] == episode["id"]
        assert episode_scoped.json()["planComplete"] is True
        episode_audit = client.get(
            f"/api/drama/projects/episodes/{episode['id']}/audit"
        )
        assert episode_audit.status_code == 200
        assert episode_audit.json()["readyForAssets"] is False
        assert any(
            issue["code"] == "episode_scene_missing"
            for issue in episode_audit.json()["issues"]
        )

        shot = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜公主寝宫｜夜"},
        ).json()
        created_shot = client.post(
            f"/api/drama/projects/scenes/{shot['id']}/shots",
            json={"title": "铜镜发现"},
        ).json()
        attached = client.patch(
            f"/api/drama/projects/shots/{created_shot['id']}",
            json={
                "grid9AssetId": "asset-grid-9",
                "storyboardAssetId": "asset-storyboard",
            },
        )
        assert attached.status_code == 200
        assert attached.json()["grid9AssetId"] == "asset-grid-9"
        assert (
            attached.json()["storyboardAssetId"] == "asset-storyboard"
        )

        entity = client.post(
            f"/api/drama/projects/{project_id}/entities",
            json={
                "kind": "character",
                "name": "宋宁公主",
                "description": "宋制公主造型",
            },
        ).json()
        with_slots = client.patch(
            f"/api/drama/projects/entities/{entity['id']}",
            json={
                "name": "宋宁公主",
                "description": "宋制公主造型",
                "status": "draft",
                "primaryAssetId": None,
                "referenceAssetIds": [],
                "assetSlots": {
                    "turnaround_front": "asset-char-front",
                    "turnaround_back": "asset-char-back",
                },
            },
        )
        assert with_slots.status_code == 200
        assert (
            with_slots.json()["assetSlots"]["turnaround_front"]
            == "asset-char-front"
        )

        script = client.post(
            f"/api/drama/projects/{project_id}/documents",
            json={
                "kind": "script",
                "title": "剧本",
                "content": (
                    "第 1 集\n场 1｜内景｜公主寝宫｜夜\n"
                    "宋宁公主：画像里为什么有我？"
                ),
            },
        )
        assert script.status_code == 200

        for role_id in ("screenwriter", "director"):
            review = client.post(
                f"/api/drama/projects/{project_id}/reviews",
                json={
                    "stage": "script",
                    "roleId": role_id,
                    "status": "passed",
                    "score": 90,
                    "checklist": [
                        {
                            "key": "structure",
                            "label": "结构完整",
                            "passed": True,
                            "note": "",
                        }
                    ],
                    "feedback": "可以进入用户确认。",
                    "reviewer": "agent",
                },
            )
            assert review.status_code == 200

        control = client.get(
            f"/api/drama/projects/{project_id}/production-control"
        )
        assert control.status_code == 200
        script_gate = control.json()["currentStage"]
        assert script_gate["agentReady"] is True
        assert script_gate["status"] == "awaiting_user"
        assert control.json()["episodes"][0]["planComplete"] is True

        approved = client.post(
            f"/api/drama/projects/{project_id}/stages/script/approve",
            json={"feedback": "剧本方向和拆解可以。"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        project_after = client.get(
            f"/api/drama/projects/{project_id}"
        ).json()
        assert project_after["activeStage"] == "breakdown"

        stale_script = client.post(
            f"/api/drama/projects/{project_id}/documents",
            json={
                "kind": "script",
                "title": "剧本 v2",
                "content": "第 1 集\n场 1｜内景｜公主寝宫｜夜\n内容已修改。",
            },
        )
        assert stale_script.status_code == 200
        control_after_change = client.get(
            f"/api/drama/projects/{project_id}/production-control"
        ).json()
        script_gate = next(
            gate
            for gate in control_after_change["gates"]
            if gate["stage"] == "script"
        )
        assert script_gate["approved"] is False
        assert script_gate["stale"] is True
        assert "变更" in script_gate["label"]
        blocked_approval = client.post(
            f"/api/drama/projects/{project_id}/stages/script/approve",
            json={"feedback": "旧审核不应直接复用。"},
        )
        assert blocked_approval.status_code == 400
        assert "重新审核" in blocked_approval.json()["detail"]

    restarted = create_app(FakeCodexClient(), database_path=tmp_path / "drama.db")
    with TestClient(restarted) as client:
        restored = client.get(
            f"/api/drama/projects/{project_id}/production-control"
        ).json()
        assert restored["currentStage"]["stage"] == "breakdown"
        script = next(
            gate for gate in restored["gates"] if gate["stage"] == "script"
        )
        assert script["approved"] is False
        assert script["stale"] is True
        assert restored["episodes"][0]["plan"]["locations"] == [
            "公主寝宫",
            "宫墙",
        ]


def test_bind_drama_assets_validates_media_type(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "drama.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "素材绑定测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜测试｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "测试镜头"},
        ).json()
        entity = client.post(
            f"/api/drama/projects/{project['id']}/entities",
            json={"kind": "character", "name": "测试角色"},
        ).json()
        image_upload = client.post(
            "/api/assets/upload",
            files={"files": ("view.png", b"image-bytes", "image/png")},
        )
        assert image_upload.status_code == 200
        image_id = image_upload.json()["assetIds"][0]

        entity_bound = client.put(
            f"/api/drama/projects/entities/{entity['id']}"
            "/asset-slots/turnaround_front",
            json={"assetId": image_id},
        )
        assert entity_bound.status_code == 200
        assert (
            entity_bound.json()["assetSlots"]["turnaround_front"] == image_id
        )

        shot_bound = client.put(
            f"/api/drama/projects/shots/{shot['id']}/asset-slots/grid9",
            json={"assetId": image_id},
        )
        assert shot_bound.status_code == 200
        assert shot_bound.json()["grid9AssetId"] == image_id
        assert shot_bound.json()["status"] == "keyframe_ready"
        no_video_approval = client.patch(
            f"/api/drama/projects/shots/{shot['id']}",
            json={"status": "approved"},
        )
        assert no_video_approval.status_code == 400
        assert "没有视频" in no_video_approval.json()["detail"]

        wrong_type = client.put(
            f"/api/drama/projects/shots/{shot['id']}/asset-slots/video",
            json={"assetId": image_id},
        )
        assert wrong_type.status_code == 400
        assert "video" in wrong_type.json()["detail"]

        video_upload = client.post(
            "/api/assets/upload",
            files={"files": ("clip.mp4", b"video-bytes", "video/mp4")},
        )
        video_id = video_upload.json()["assetIds"][0]
        video_bound = client.put(
            f"/api/drama/projects/shots/{shot['id']}/asset-slots/video",
            json={"assetId": video_id},
        )
        assert video_bound.status_code == 200
        assert video_bound.json()["videoAssetId"] == video_id
        assert video_bound.json()["status"] == "clip_ready"
        approved = client.patch(
            f"/api/drama/projects/shots/{shot['id']}",
            json={"status": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        approval_history = client.get(
            f"/api/drama/projects/shots/{shot['id']}/status-history"
        )
        assert approval_history.status_code == 200
        assert approval_history.json()["events"][0]["reviewer"] == "user"
        assert approval_history.json()["events"][0]["toStatus"] == "approved"
        replacement_upload = client.post(
            "/api/assets/upload",
            files={"files": ("replacement.mp4", b"replacement", "video/mp4")},
        )
        replacement_id = replacement_upload.json()["assetIds"][0]
        replaced = client.put(
            f"/api/drama/projects/shots/{shot['id']}/asset-slots/video",
            json={"assetId": replacement_id},
        )
        assert replaced.status_code == 200
        assert replaced.json()["status"] == "clip_ready"
        history = client.get(
            f"/api/drama/projects/shots/{shot['id']}/status-history"
        ).json()["events"]
        assert history[0]["reviewer"] == "system"
        assert history[0]["fromStatus"] == "approved"
        assert history[0]["toStatus"] == "clip_ready"


def test_shot_asset_candidates_preserve_history_and_can_be_reselected(
    tmp_path,
) -> None:
    database_path = tmp_path / "candidates.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "候选历史测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜候选测试｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "候选镜头"},
        ).json()
        first_upload = client.post(
            "/api/assets/upload",
            files={"files": ("first.png", b"first-image", "image/png")},
        )
        second_upload = client.post(
            "/api/assets/upload",
            files={"files": ("second.png", b"second-image", "image/png")},
        )
        first_asset = first_upload.json()["assetIds"][0]
        second_asset = second_upload.json()["assetIds"][0]

        first_bind = client.put(
            f"/api/drama/projects/shots/{shot['id']}"
            "/asset-slots/first_frame",
            json={"assetId": first_asset},
        )
        assert first_bind.status_code == 200
        first_candidate = first_bind.json()["candidates"][0]
        assert first_candidate["assetId"] == first_asset
        assert first_candidate["status"] == "selected"

        second_bind = client.put(
            f"/api/drama/projects/shots/{shot['id']}"
            "/asset-slots/first_frame",
            json={"assetId": second_asset},
        )
        assert second_bind.status_code == 200
        candidates = second_bind.json()["candidates"]
        assert len(candidates) == 2
        statuses = {
            candidate["assetId"]: candidate["status"]
            for candidate in candidates
        }
        assert statuses[first_asset] == "superseded"
        assert statuses[second_asset] == "selected"

        reselected = client.patch(
            f"/api/drama/projects/asset-candidates/{first_candidate['id']}",
            json={"status": "selected"},
        )
        assert reselected.status_code == 200
        assert reselected.json()["status"] == "selected"

        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        persisted = production[0]["scenes"][0]["shots"][0]["candidates"]
        statuses = {
            candidate["assetId"]: candidate["status"]
            for candidate in persisted
        }
        assert statuses[first_asset] == "selected"
        assert statuses[second_asset] == "superseded"

        reject_selected = client.patch(
            f"/api/drama/projects/asset-candidates/{first_candidate['id']}",
            json={"status": "rejected"},
        )
        assert reject_selected.status_code == 400
        assert "先选择其他候选" in reject_selected.json()["detail"]

    restarted = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(restarted) as client:
        candidates = client.get(
            f"/api/drama/projects/{project['id']}/asset-candidates"
            f"?subjectId={shot['id']}&slot=first_frame"
        )
        assert candidates.status_code == 200
        assert {
            candidate["status"] for candidate in candidates.json()
        } == {"selected", "superseded"}


def test_shot_prompt_overrides_persist_and_invalidate_keyframes(
    tmp_path,
) -> None:
    database_path = tmp_path / "shot-prompts.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "提示词持久化测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜提示词｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "提示词镜头"},
        ).json()
        before = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()
        before_keyframe_revision = next(
            gate["revision"]
            for gate in before["gates"]
            if gate["stage"] == "keyframes"
        )
        before_clip_revision = next(
            gate["revision"]
            for gate in before["gates"]
            if gate["stage"] == "clips"
        )
        saved = client.put(
            f"/api/drama/projects/shots/{shot['id']}/prompts/video",
            json={"prompt": "镜头缓慢推进，窗外竹影轻摆。"},
        )
        assert saved.status_code == 200
        assert (
            saved.json()["promptOverrides"]["video"]
            == "镜头缓慢推进，窗外竹影轻摆。"
        )
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        assert (
            production[0]["scenes"][0]["shots"][0]["promptOverrides"][
                "video"
            ]
            == "镜头缓慢推进，窗外竹影轻摆。"
        )
        after = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()
        after_keyframe_revision = next(
            gate["revision"]
            for gate in after["gates"]
            if gate["stage"] == "keyframes"
        )
        after_clip_revision = next(
            gate["revision"]
            for gate in after["gates"]
            if gate["stage"] == "clips"
        )
        assert after_keyframe_revision == before_keyframe_revision
        assert after_clip_revision == before_clip_revision + 1

    restarted = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(restarted) as client:
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        assert (
            production[0]["scenes"][0]["shots"][0]["promptOverrides"][
                "video"
            ]
            == "镜头缓慢推进，窗外竹影轻摆。"
        )


def test_entity_prompt_overrides_persist_and_invalidate_assets(
    tmp_path,
) -> None:
    database_path = tmp_path / "entity-prompts.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "资产提示词持久化测试"},
        ).json()
        entity = client.post(
            f"/api/drama/projects/{project['id']}/entities",
            json={
                "kind": "character",
                "name": "宋宁公主",
                "description": "宋制公主造型",
            },
        ).json()
        before = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()
        before_revision = next(
            gate["revision"]
            for gate in before["gates"]
            if gate["stage"] == "assets"
        )
        saved = client.put(
            f"/api/drama/projects/entities/{entity['id']}"
            "/prompts/turnaround_front",
            json={"prompt": "正面全身，月白交领，深青褙子，表情克制。"},
        )
        assert saved.status_code == 200
        assert (
            saved.json()["assetPrompts"]["turnaround_front"]
            == "正面全身，月白交领，深青褙子，表情克制。"
        )
        after = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()
        after_revision = next(
            gate["revision"]
            for gate in after["gates"]
            if gate["stage"] == "assets"
        )
        assert after_revision == before_revision + 1

    restarted = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(restarted) as client:
        entities = client.get(
            f"/api/drama/projects/{project['id']}/entities"
        ).json()
        assert (
            entities[0]["assetPrompts"]["turnaround_front"]
            == "正面全身，月白交领，深青褙子，表情克制。"
        )


def test_production_run_tracks_partial_failure_and_retries(
    tmp_path,
) -> None:
    database_path = tmp_path / "production-run.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "批量制作运行测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        _complete_episode_plan(client, episode["id"])
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜制作运行｜夜"},
        ).json()
        first_shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "镜头一",
                "description": "人物在窗边停下并看向铜镜。",
            },
        ).json()
        second_shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "镜头二",
                "description": "竹影在窗纸上缓慢移动。",
            },
        ).json()
        first_upload = client.post(
            "/api/assets/upload",
            files={"files": ("one.png", b"one-image", "image/png")},
        ).json()["assetIds"][0]
        second_upload = client.post(
            "/api/assets/upload",
            files={"files": ("two.png", b"two-image", "image/png")},
        ).json()["assetIds"][0]

    app = create_app(
        FakeCodexClient(),
        database_path=database_path,
        production_media=FakeProductionMedia([first_upload, second_upload]),
    )
    with TestClient(app) as client:
        created = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{episode['id']}/production-runs",
            json={
                "stage": "keyframes",
                "name": "第 1 集首帧批处理",
                "requiresApproval": True,
                "maxParallel": 2,
                "items": [
                    {
                        "targetType": "shot",
                        "targetId": first_shot["id"],
                        "slot": "first_frame",
                        "title": "镜头一首帧",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "生成镜头一首帧",
                        },
                    },
                    {
                        "targetType": "shot",
                        "targetId": second_shot["id"],
                        "slot": "first_frame",
                        "title": "镜头二首帧",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "FAIL 生成镜头二首帧",
                        },
                    },
                ],
            },
        )
        assert created.status_code == 200
        run = created.json()
        assert run["status"] == "awaiting_approval"
        run_id = run["id"]
        started = client.post(
            f"/api/drama/projects/production-runs/{run_id}/start",
            json={"approvedBy": "test-user"},
        )
        assert started.status_code == 200

        run = _wait_for_run(client, run_id, {"partial"})
        assert run["counts"]["succeeded"] == 1
        assert run["counts"]["failed"] == 1
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        shots = production[0]["scenes"][0]["shots"]
        assert shots[0]["firstFrameAssetId"] is not None
        assert shots[1]["firstFrameAssetId"] is None

        client.put(
            f"/api/drama/projects/episodes/{episode['id']}/plan",
            json={},
        )
        retry_blocked = client.post(
            f"/api/drama/projects/production-runs/{run_id}/retry-failed",
            json={"approvedBy": "test-user"},
        )
        assert retry_blocked.status_code == 400
        assert "分集检查未通过" in retry_blocked.json()["detail"]

        _complete_episode_plan(client, episode["id"])
        retried = client.post(
            f"/api/drama/projects/production-runs/{run_id}/retry-failed",
            json={"approvedBy": "test-user"},
        )
        assert retried.status_code == 200
        run = _wait_for_run(client, run_id, {"completed"})
        assert run["counts"]["succeeded"] == 2
        assert run["counts"]["failed"] == 0
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        shots = production[0]["scenes"][0]["shots"]
        assert all(shot["firstFrameAssetId"] for shot in shots)


def test_production_run_binds_entity_primary_and_advances_revision(
    tmp_path,
) -> None:
    database_path = tmp_path / "asset-run.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "资产主图运行测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        _complete_episode_plan(client, episode["id"], location="资产测试")
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜资产测试｜夜"},
        ).json()
        client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "资产测试镜头",
                "description": "人物和场景用于资产绑定测试。",
            },
        )
        entity = client.post(
            f"/api/drama/projects/{project['id']}/entities",
            json={
                "kind": "character",
                "name": "测试角色",
                "description": "用于验证主图绑定。",
            },
        ).json()
        asset_id = client.post(
            "/api/assets/upload",
            files={"files": ("primary.png", b"primary-image", "image/png")},
        ).json()["assetIds"][0]
        before = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()
        before_revision = next(
            gate["revision"]
            for gate in before["gates"]
            if gate["stage"] == "assets"
        )

    media = FakeProductionMedia([asset_id])
    app = create_app(
        FakeCodexClient(),
        database_path=database_path,
        production_media=media,
    )
    with TestClient(app) as client:
        created = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{episode['id']}/production-runs",
            json={
                "stage": "assets",
                "name": "角色主图",
                "requiresApproval": True,
                "items": [
                    {
                        "targetType": "entity",
                        "targetId": entity["id"],
                        "slot": "primary",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "生成角色主图",
                        },
                    }
                ],
            },
        )
        assert created.status_code == 200
        run_id = created.json()["id"]
        client.post(
            f"/api/drama/projects/production-runs/{run_id}/start",
            json={"approvedBy": "test-user"},
        )
        run = _wait_for_run(client, run_id, {"completed"})
        entities = client.get(
            f"/api/drama/projects/{project['id']}/entities"
        ).json()
        after = client.get(
            f"/api/drama/projects/{project['id']}/production-control"
        ).json()

    after_revision = next(
        gate["revision"]
        for gate in after["gates"]
        if gate["stage"] == "assets"
    )
    assert run["counts"]["succeeded"] == 1
    assert run["items"][0]["resultAssetId"] == asset_id
    assert entities[0]["primaryAssetId"] == asset_id
    assert after_revision == before_revision + 1
    origin = media.requests[0]["origin"]
    assert origin["kind"] == "drama_production_run"
    assert origin["projectId"] == project["id"]
    assert origin["episodeId"] == episode["id"]
    assert origin["productionRunId"] == run_id
    assert origin["targetId"] == entity["id"]
    assert origin["slot"] == "primary"


def test_production_run_resumes_after_api_restart(tmp_path) -> None:
    database_path = tmp_path / "production-resume.db"
    app = create_app(FakeCodexClient(), database_path=database_path)
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "重启续接测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        _complete_episode_plan(client, episode["id"], location="重启测试")
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜重启测试｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "重启镜头",
                "description": "人物在竹影前缓慢转身。",
            },
        ).json()
        asset_id = client.post(
            "/api/assets/upload",
            files={"files": ("resume.png", b"resume-image", "image/png")},
        ).json()["assetIds"][0]

    media = RestartableProductionMedia(asset_id)
    app = create_app(
        FakeCodexClient(),
        database_path=database_path,
        production_media=media,
    )
    with TestClient(app) as client:
        run = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{episode['id']}/production-runs",
            json={
                "stage": "keyframes",
                "name": "重启续接",
                "requiresApproval": True,
                "items": [
                    {
                        "targetType": "shot",
                        "targetId": shot["id"],
                        "slot": "first_frame",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "重启测试首帧",
                        },
                    }
                ],
            },
        ).json()
        run_id = run["id"]
        client.post(
            f"/api/drama/projects/production-runs/{run_id}/start",
            json={"approvedBy": "test-user"},
        )
        running = _wait_for_run(client, run_id, {"running"})
        assert running["items"][0]["generationTaskId"].startswith(
            "restart-task-"
        )

    media.complete_all()
    restarted = create_app(
        FakeCodexClient(),
        database_path=database_path,
        production_media=media,
    )
    with TestClient(restarted) as client:
        completed = _wait_for_run(client, run_id, {"completed"})
        assert completed["counts"]["succeeded"] == 1
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
        assert (
            production[0]["scenes"][0]["shots"][0]["firstFrameAssetId"]
            == asset_id
        )


def test_production_run_rejects_incomplete_episode_plan(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "run-gate.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "制作运行质量门测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜质量门｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "质量门镜头", "description": "人物在镜前停下动作。"},
        ).json()
        run_payload = {
            "stage": "keyframes",
            "name": "未通过质量门的运行",
            "requiresApproval": True,
            "items": [
                {
                    "targetType": "shot",
                    "targetId": shot["id"],
                    "slot": "first_frame",
                    "request": {
                        "providerId": "fake",
                        "modelId": "image-model",
                        "taskType": "image_generation",
                        "prompt": "生成首帧",
                    },
                }
            ],
        }
        blocked = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{episode['id']}/production-runs",
            json=run_payload,
        )
        assert blocked.status_code == 400
        assert "分集检查未通过" in blocked.json()["detail"]

        _complete_episode_plan(client, episode["id"], location="质量门")
        created = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{episode['id']}/production-runs",
            json=run_payload,
        )
        assert created.status_code == 200
        run_id = created.json()["id"]

        client.put(
            f"/api/drama/projects/episodes/{episode['id']}/plan",
            json={},
        )
        start_blocked = client.post(
            f"/api/drama/projects/production-runs/{run_id}/start",
            json={"approvedBy": "test-user"},
        )
        assert start_blocked.status_code == 400
        assert "分集检查未通过" in start_blocked.json()["detail"]


def test_episode_production_runs_and_shots_stay_isolated(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "episode-scope.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "多集隔离测试"},
        ).json()
        first_episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集", "synopsis": "第一集"},
        ).json()
        second_episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 2 集", "synopsis": "第二集"},
        ).json()
        _complete_episode_plan(client, first_episode["id"], location="第一集场景")
        _complete_episode_plan(client, second_episode["id"], location="第二集场景")

        first_scene = client.post(
            f"/api/drama/projects/episodes/{first_episode['id']}/scenes",
            json={"heading": "内景｜第一集场景｜夜"},
        ).json()
        second_scene = client.post(
            f"/api/drama/projects/episodes/{second_episode['id']}/scenes",
            json={"heading": "内景｜第二集场景｜夜"},
        ).json()
        first_shot = client.post(
            f"/api/drama/projects/scenes/{first_scene['id']}/shots",
            json={
                "title": "第一集镜头",
                "description": "第一集人物在镜前转身。",
            },
        ).json()
        second_shot = client.post(
            f"/api/drama/projects/scenes/{second_scene['id']}/shots",
            json={
                "title": "第二集镜头",
                "description": "第二集人物在窗边停步。",
            },
        ).json()

        run = client.post(
            f"/api/drama/projects/{project['id']}/episodes/"
            f"{first_episode['id']}/production-runs",
            json={
                "stage": "keyframes",
                "name": "第一集首帧",
                "items": [
                    {
                        "targetType": "shot",
                        "targetId": first_shot["id"],
                        "slot": "first_frame",
                        "request": {
                            "providerId": "fake",
                            "modelId": "image-model",
                            "taskType": "image_generation",
                            "prompt": "第一集首帧",
                        },
                    }
                ],
            },
        )
        assert run.status_code == 200

        first_runs = client.get(
            f"/api/drama/projects/{project['id']}/production-runs"
            f"?episodeId={first_episode['id']}"
        ).json()
        second_runs = client.get(
            f"/api/drama/projects/{project['id']}/production-runs"
            f"?episodeId={second_episode['id']}"
        ).json()
        first_production = client.get(
            f"/api/drama/projects/episodes/{first_episode['id']}/production"
        ).json()
        second_production = client.get(
            f"/api/drama/projects/episodes/{second_episode['id']}/production"
        ).json()

    assert [item["id"] for item in first_runs] == [run.json()["id"]]
    assert second_runs == []
    assert first_production["id"] == first_episode["id"]
    assert first_production["scenes"][0]["shots"][0]["id"] == first_shot["id"]
    assert second_production["id"] == second_episode["id"]
    assert second_production["scenes"][0]["shots"][0]["id"] == second_shot["id"]


def test_series_production_summarizes_multi_episode_video_progress(
    tmp_path,
) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "series.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "多集总览测试"},
        ).json()
        first_episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        second_episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 2 集"},
        ).json()
        _complete_episode_plan(client, first_episode["id"], location="第一集")
        _complete_episode_plan(client, second_episode["id"], location="第二集")
        first_scene = client.post(
            f"/api/drama/projects/episodes/{first_episode['id']}/scenes",
            json={"heading": "内景｜第一集｜夜"},
        ).json()
        second_scene = client.post(
            f"/api/drama/projects/episodes/{second_episode['id']}/scenes",
            json={"heading": "内景｜第二集｜夜"},
        ).json()
        first_shot = client.post(
            f"/api/drama/projects/scenes/{first_scene['id']}/shots",
            json={
                "title": "第一集镜头",
                "description": "第一集人物在窗边转身。",
            },
        ).json()
        client.post(
            f"/api/drama/projects/scenes/{second_scene['id']}/shots",
            json={
                "title": "第二集镜头",
                "description": "第二集人物在门前停下。",
            },
        )
        image_id = client.post(
            "/api/assets/upload",
            files={"files": ("frame.png", b"frame", "image/png")},
        ).json()["assetIds"][0]
        video_id = client.post(
            "/api/assets/upload",
            files={"files": ("clip.mp4", b"clip", "video/mp4")},
        ).json()["assetIds"][0]
        client.put(
            f"/api/drama/projects/shots/{first_shot['id']}"
            "/asset-slots/first_frame",
            json={"assetId": image_id},
        )
        client.put(
            f"/api/drama/projects/shots/{first_shot['id']}"
            "/asset-slots/video",
            json={"assetId": video_id},
        )
        series = client.get(
            f"/api/drama/projects/{project['id']}/series-production"
        )

    assert series.status_code == 200
    data = series.json()
    assert data["totals"]["episodes"] == 2
    assert data["totals"]["plansComplete"] == 2
    assert data["totals"]["shots"] == 2
    assert data["totals"]["keyframesReady"] == 1
    assert data["totals"]["videosReady"] == 1
    assert data["totals"]["episodesReadyToAdvance"] == 2
    assert data["episodes"][0]["nextAction"] == "review_shots"
    assert data["episodes"][0]["queueState"] == "ready"
    assert data["episodes"][0]["missingVideos"] == []
    assert data["episodes"][0]["unreviewedShots"][0]["title"] == "第一集镜头"
    assert data["episodes"][0]["gates"]["breakdown"]["approved"] is True
    assert data["episodes"][0]["gates"]["assets"]["status"] == "pending"
    assert data["episodes"][0]["gates"]["keyframes"]["approved"] is True
    assert data["episodes"][0]["gates"]["clips"]["approved"] is False
    assert data["episodes"][1]["nextAction"] == "generate_keyframes"
    assert data["episodes"][1]["missingKeyframes"][0]["title"] == "第二集镜头"
    assert data["episodes"][1]["gates"]["keyframes"]["approved"] is False


def test_script_audit_detects_structure_and_placeholders(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "script.db")
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "剧本审核测试"},
        ).json()
        script = client.post(
            f"/api/drama/projects/{project['id']}/documents",
            json={
                "kind": "script",
                "title": "剧本",
                "content": (
                    "第 1 集 重逢\n\n"
                    "场 1｜内景｜旧教室｜日\n"
                    "林微走到讲台，从粉笔槽里抽出那封信，指尖停住。\n"
                    "林微：这封信是谁写的？\n"
                ),
            },
        ).json()
        valid = client.get(
            f"/api/drama/projects/{project['id']}/script-audit"
        )
        assert valid.status_code == 200
        assert valid.json()["episodeCount"] == 1
        assert valid.json()["sceneCount"] == 1
        assert valid.json()["dialogueLineCount"] == 1
        assert valid.json()["craftSummary"]["actionlessDialogueSceneCount"] == 0
        assert valid.json()["readyForReview"] is True

        client.patch(
            f"/api/drama/projects/documents/{script['id']}",
            json={
                "title": "剧本",
                "content": "第 1 集 重逢\n\n场 1｜内景｜旧教室｜日\n待填写对白",
            },
        )
        invalid = client.get(
            f"/api/drama/projects/{project['id']}/script-audit"
        )
        assert invalid.status_code == 200
        assert invalid.json()["placeholderCount"] == 1
        assert invalid.json()["readyForReview"] is False
        assert any(
            issue["code"] == "script_dialogue_missing"
            for issue in invalid.json()["issues"]
        )

        client.patch(
            f"/api/drama/projects/documents/{script['id']}",
            json={
                "title": "剧本",
                "content": (
                    "第 1 集 重逢\n\n"
                    "场 1｜内景｜旧教室｜日\n"
                    "林微："
                    + "我必须把这件事从头到尾解释清楚，" * 8
                    + "\n"
                    "周岚：然后呢？\n"
                    "林微：你听我说完。\n"
                    "周岚：我在听。\n"
                    "林微：事情不是你想的那样。\n"
                    "周岚：那是哪样？\n"
                    "林微：你先别问。\n"
                ),
            },
        )
        craft = client.get(
            f"/api/drama/projects/{project['id']}/script-audit"
        )
        assert craft.status_code == 200
        assert craft.json()["craftSummary"]["overwrittenDialogueCount"] == 1
        assert craft.json()["craftSummary"]["actionlessDialogueSceneCount"] == 1
        assert craft.json()["craftSummary"]["longDialogueRunSceneCount"] == 1
        assert craft.json()["readyForReview"] is False
        craft_codes = {
            issue["code"] for issue in craft.json()["issues"]
        }
        assert {
            "script_scene_action_missing",
            "script_dialogue_overwritten",
            "script_dialogue_run_long",
        }.issubset(craft_codes)


def test_character_creation_profile_persists_across_asset_updates(tmp_path) -> None:
    app = create_app(
        FakeCodexClient(),
        database_path=tmp_path / "character-profile.db",
    )
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "人物创作档案测试"},
        ).json()
        profile = {
            "want": "拿回被抹去的身份",
            "need": "承认自己也会害怕",
            "falseBelief": "只有掌控一切才安全",
            "speechPattern": "短句、少解释、回答问题前先停顿",
            "bodyBehavior": "紧张时用拇指摩挲玉佩边缘",
        }
        entity = client.post(
            f"/api/drama/projects/{project['id']}/entities",
            json={
                "kind": "character",
                "name": "宋宁公主",
                "description": "宋制公主造型",
                "profile": profile,
            },
        ).json()
        assert entity["profile"] == profile

        updated = client.patch(
            f"/api/drama/projects/entities/{entity['id']}",
            json={
                "name": "宋宁公主",
                "description": "补充月白交领细节",
                "status": "draft",
                "primaryAssetId": None,
                "referenceAssetIds": [],
                "assetSlots": {},
            },
        )

    assert updated.status_code == 200
    assert updated.json()["profile"] == profile


def test_episode_plan_persists_scene_contracts(tmp_path) -> None:
    app = create_app(
        FakeCodexClient(),
        database_path=tmp_path / "scene-contracts.db",
    )
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "场景契约测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        response = client.put(
            f"/api/drama/projects/episodes/{episode['id']}/plan",
            json={
                "timeScope": "北宋某夜",
                "locations": ["寝宫"],
                "interiorExterior": ["内景"],
                "characters": ["宋宁"],
                "scenes": ["发现画像"],
                "storyBeats": ["触碰画像", "记忆闪回"],
                "visualRequirements": ["铜镜反光"],
                "dialogueRequirements": ["克制"],
                "continuityRisks": ["画像身份"],
                "sceneContracts": [
                    {
                        "sceneNumber": 1,
                        "title": "铜镜前的发现",
                        "valueIn": "安全",
                        "characterObjectives": ["宋宁：确认画像来源"],
                        "obstacle": "画像中的衣饰与记忆互相矛盾",
                        "tactics": ["试探", "逼近观察"],
                        "beats": ["发现", "迟疑", "触碰"],
                        "turn": "画像出现她从未见过的服饰",
                        "valueOut": "暴露风险",
                        "subtext": "她害怕自己遗忘的不是事，而是另一个人",
                        "visualStrategy": "镜中反射与真实空间错位",
                        "performanceNotes": "先控制呼吸，触碰前手指停顿",
                        "soundNotes": "竹影声突然停止",
                    }
                ],
            },
        )

    assert response.status_code == 200
    contract = response.json()["plan"]["sceneContracts"][0]
    assert contract["sceneNumber"] == 1
    assert contract["valueIn"] == "安全"
    assert contract["valueOut"] == "暴露风险"
    assert contract["characterObjectives"] == ["宋宁：确认画像来源"]


def test_shot_direction_persists_and_updates_structured_notes(tmp_path) -> None:
    app = create_app(
        FakeCodexClient(),
        database_path=tmp_path / "shot-direction.db",
    )
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "镜头导演设计测试"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜寝宫｜夜"},
        ).json()
        shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={
                "title": "触碰铜镜",
                "description": "公主伸手触碰铜镜。",
                "direction": {
                    "shotSize": "中近景",
                    "cameraAngle": "平视略低",
                    "cameraMovement": "极慢推近",
                    "blocking": "人物从窗边转向铜镜",
                    "performanceAction": "呼吸收紧后伸手",
                    "lighting": "窗侧月光与暖烛补光",
                },
            },
        ).json()
        updated = client.put(
            f"/api/drama/projects/shots/{shot['id']}/direction",
            json={
                "shotSize": "特写",
                "cameraAngle": "俯拍",
                "cameraMovement": "静止",
                "lens": "85mm",
                "blocking": "手指悬停在镜面朱砂印记前",
                "performanceAction": "停顿两拍后触碰",
                "expression": "迟疑转为惊恐",
                "composition": "铜镜占画面右侧三分之二",
                "lighting": "月光侧逆光，脸部保留暖烛补光",
                "sound": "竹影声突然停止",
                "transition": "动作中切",
                "referenceNotes": "与首帧保持同一发饰和衣纹方向",
            },
        )

    assert shot["direction"]["shotSize"] == "中近景"
    assert updated.status_code == 200
    assert updated.json()["direction"]["shotSize"] == "特写"
    assert updated.json()["direction"]["cameraMovement"] == "静止"
    assert updated.json()["direction"]["sound"] == "竹影声突然停止"


def test_episode_render_requires_clips_and_persists_export(tmp_path) -> None:
    database_path = tmp_path / "drama.db"
    renderer = FakeTimelineRenderer()
    app = create_app(
        FakeCodexClient(),
        database_path=database_path,
        timeline_renderer=renderer,
    )
    with TestClient(app) as client:
        project = client.post(
            "/api/drama/projects",
            json={"idea": "整集合成测试", "format": "9:16"},
        ).json()
        episode = client.post(
            f"/api/drama/projects/{project['id']}/episodes",
            json={"title": "第 1 集"},
        ).json()
        scene = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/scenes",
            json={"heading": "内景｜测试｜夜"},
        ).json()
        first_shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "镜头一", "dialogue": "第一句对白"},
        ).json()
        second_shot = client.post(
            f"/api/drama/projects/scenes/{scene['id']}/shots",
            json={"title": "镜头二", "dialogue": "第二句对白"},
        ).json()
        missing = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/render"
        )
        assert missing.status_code == 400
        assert "缺少视频" in missing.json()["detail"]

        client.patch(
            f"/api/drama/projects/shots/{first_shot['id']}",
            json={"videoAssetId": "clip-1"},
        )
        client.patch(
            f"/api/drama/projects/shots/{second_shot['id']}",
            json={"videoAssetId": "clip-2"},
        )
        unapproved_render = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/render"
        )
        assert unapproved_render.status_code == 400
        assert "尚未通过审核" in unapproved_render.json()["detail"]
        for shot_id in (first_shot["id"], second_shot["id"]):
            approved_shot = client.patch(
                f"/api/drama/projects/shots/{shot_id}",
                json={"status": "approved"},
            )
            assert approved_shot.status_code == 200
        subtitles = client.put(
            f"/api/drama/projects/episodes/{episode['id']}/subtitles",
            json={
                "cues": [
                    {
                        "startSeconds": 0,
                        "endSeconds": 2.5,
                        "text": "自定义字幕",
                    }
                ]
            },
        )
        assert subtitles.status_code == 200
        assert subtitles.json()["cues"][0]["text"] == "自定义字幕"
        mix = client.put(
            f"/api/drama/projects/episodes/{episode['id']}/audio-mix",
            json={
                "musicAssetId": "music-1",
                "musicVolumeDb": -20,
                "ambienceAssetId": "ambience-1",
                "ambienceVolumeDb": -24,
                "ducking": False,
                "soundEffects": [
                    {
                        "assetId": "sfx-1",
                        "startSeconds": 1.2,
                        "durationSeconds": 0.8,
                        "volumeDb": -12,
                    }
                ],
            },
        )
        assert mix.status_code == 200
        assert mix.json()["musicAssetId"] == "music-1"
        style = client.put(
            f"/api/drama/projects/episodes/{episode['id']}/subtitle-style",
            json={
                "preset": "cinema",
                "fontSize": 36,
                "outline": 2.5,
                "marginV": 120,
                "primaryColor": "#FFF4E5",
                "outlineColor": "#101418",
            },
        )
        assert style.status_code == 200
        assert style.json()["preset"] == "cinema"
        rendered = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/render"
        )
        assert rendered.status_code == 200
        assert rendered.json()["exportAssetId"] == "episode-export"
        assert rendered.json()["status"] == "rendered"
        manifest_id = rendered.json()["exportManifestId"]
        assert manifest_id
        manifest = rendered.json()["exportManifest"]
        assert manifest["schemaVersion"] == 1
        assert manifest["rendering"]["shotOrder"] == [
            first_shot["id"],
            second_shot["id"],
        ]
        assert manifest["approvalComplete"] is False
        assert {
            gate["stage"] for gate in manifest["approvalWarnings"]
        }
        manifests = client.get(
            f"/api/drama/projects/episodes/{episode['id']}"
            "/export-manifests"
        )
        assert manifests.status_code == 200
        assert manifests.json()[0]["id"] == manifest_id
        assert manifests.json()[0]["manifest"]["episode"]["scenes"][0][
            "shots"
        ][0]["videoAssetId"] == "clip-1"
        crossfaded = client.post(
            f"/api/drama/projects/episodes/{episode['id']}/render",
            json={
                "transition": "crossfade",
                "transitionDuration": 0.5,
            },
        )
        assert crossfaded.status_code == 200

    assert renderer.calls == [
        {
            "videoAssetIds": ["clip-1", "clip-2"],
            "aspectRatio": "9:16",
            "filename": "episode-01.mp4",
            "subtitleCues": [
                {
                    "startSeconds": 0.0,
                    "endSeconds": 2.5,
                    "text": "自定义字幕",
                }
            ],
            "audioAssetIds": [None, None],
            "subtitleStyle": {
                "preset": "cinema",
                "fontSize": 36,
                "outline": 2.5,
                "marginV": 120,
                "primaryColor": "#FFF4E5",
                "outlineColor": "#101418",
            },
            "transition": "none",
            "transitionDuration": 0.4,
            "musicAssetId": "music-1",
            "musicVolumeDb": -20.0,
            "ambienceAssetId": "ambience-1",
            "ambienceVolumeDb": -24.0,
            "ducking": False,
            "soundEffects": [
                {
                    "assetId": "sfx-1",
                    "startSeconds": 1.2,
                    "durationSeconds": 0.8,
                    "volumeDb": -12.0,
                }
            ],
        },
        {
            "videoAssetIds": ["clip-1", "clip-2"],
            "aspectRatio": "9:16",
            "filename": "episode-01.mp4",
            "subtitleCues": [
                {
                    "startSeconds": 0.0,
                    "endSeconds": 2.5,
                    "text": "自定义字幕",
                }
            ],
            "audioAssetIds": [None, None],
            "subtitleStyle": {
                "preset": "cinema",
                "fontSize": 36,
                "outline": 2.5,
                "marginV": 120,
                "primaryColor": "#FFF4E5",
                "outlineColor": "#101418",
            },
            "transition": "crossfade",
            "transitionDuration": 0.5,
            "musicAssetId": "music-1",
            "musicVolumeDb": -20.0,
            "ambienceAssetId": "ambience-1",
            "ambienceVolumeDb": -24.0,
            "ducking": False,
            "soundEffects": [
                {
                    "assetId": "sfx-1",
                    "startSeconds": 1.2,
                    "durationSeconds": 0.8,
                    "volumeDb": -12.0,
                }
            ],
        }
    ]
    restarted = create_app(
        FakeCodexClient(),
        database_path=database_path,
        timeline_renderer=FakeTimelineRenderer(),
    )
    with TestClient(restarted) as client:
        production = client.get(
            f"/api/drama/projects/{project['id']}/production"
        ).json()
    assert production[0]["exportAssetId"] == "episode-export"
    assert production[0]["status"] == "rendered"
    assert production[0]["audioMix"]["musicAssetId"] == "music-1"
    assert production[0]["subtitleStyle"]["preset"] == "cinema"
