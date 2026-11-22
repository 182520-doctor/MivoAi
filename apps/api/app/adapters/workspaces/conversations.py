"""Conversation workspace and shared read-only Agent playbooks."""

from __future__ import annotations

import re
from pathlib import Path


class ConversationWorkspaceManager:
    """Create isolated session directories under one configured root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.shared_root = self.root / "shared"
        self.sessions_root = self.root / "sessions"

    def initialize(self) -> None:
        self.shared_root.mkdir(parents=True, exist_ok=True)
        (self.shared_root / "playbooks").mkdir(parents=True, exist_ok=True)
        (self.shared_root / "tools").mkdir(parents=True, exist_ok=True)
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self._sync_shared_file(
            self.shared_root / "AGENTS.md",
            (
                "# Shared Agent Context\n\n"
                "This directory is read-only shared context for every Zaojing "
                "conversation. Session-specific work must stay in the session "
                "workspace.\n\n"
                "Use Zaojing dynamic tools for media generation, speech, "
                "processing and drama production. Do not invent tools or bypass "
                "the persisted task/project state.\n"
            ),
        )
        self._sync_shared_file(
            self.shared_root / "playbooks" / "multimodal.md",
            (
                "# Multimodal Creation Playbook\n\n"
                "1. Understand the requested modality and references.\n"
                "2. Call `zaojing_discover_media_models` before choosing a model.\n"
                "3. Pass ordered modality arrays; never expose ComfyUI node IDs.\n"
                "4. Use canonical parameters rather than provider node fields.\n"
                "5. Submit through `zaojing_generate_media` and wait for results.\n"
                "Retry only failed or canceled media requests with "
                "`zaojing_retry_media_tasks`, and make batch retries an explicit "
                "user decision. Async video tasks with a provider task ID are "
                "reconnected after an API restart instead of being resubmitted.\n"
                "6. Use `zaojing_process_media` for audio extraction, EBU R128 "
                "normalization, transcription or video upscale.\n"
                "7. Show generated assets and report the durable task ID.\n"
                "\n"
                "Use `audio_processing` for four-stem separation and "
                "`video_processing` for deterministic transforms such as "
                "transparent matting. Keep these task types separate from "
                "generation.\n"
                "\n"
                "Use `transcribe_audio` when timestamped subtitle cues are needed. "
                "The tool returns normalized cue objects and a durable JSON asset.\n"
            ),
        )
        self._sync_shared_file(
            self.shared_root / "playbooks" / "short-drama.md",
            (
                "# Short Drama Production Playbook\n\n"
                "The production flow is:\n\n"
                "brief -> story bible -> script -> per-episode plan -> shot "
                "breakdown -> character/location/prop/costume/style assets -> "
                "keyframes, nine-grid, storyboard -> clips/audio -> timeline.\n\n"
                "Current delivery priority: complete the multi-episode "
                "shot-video pipeline. Subtitles, editing, dubbing and final "
                "packaging remain downstream capabilities.\n\n"
                "Read `playbooks/professional-story-production.md` with "
                "`zaojing_get_shared_context` before story, script, character, "
                "directing or shot-design work. The Agent is the primary "
                "creator and self-reviewer; the user primarily audits, rejects, "
                "requests a rewrite or approves a gate. Do not turn "
                "professional fields back into a form for the user to complete.\n\n"
                "1. Read the project and current gate with "
                "`zaojing_get_drama_control_room`.\n"
                "2. Before writing, read the relevant professional handbook "
                "with `zaojing_get_drama_roles`.\n"
                "When the user is working inside one episode, read only that "
                "episode with `zaojing_get_drama_episode`; do not load every "
                "episode unless the user asks for a cross-episode review.\n"
                "After creating or revising an episode plan, call "
                "`zaojing_audit_drama_episode` and fix every deterministic "
                "error before requesting user approval.\n"
                "3. Confirm the irreversible creative frame once: audience, "
                "story promise, visual style, episode count, duration, content "
                "limits, production constraints and ending tendency. After that "
                "frame is approved, make professional choices and interrupt only "
                "for a material fork, rights/content risk, cost or explicit "
                "user rejection.\n"
                "4. Save authoring drafts with `zaojing_save_drama_draft`; "
                "Agent drafts are never user-approved automatically.\n"
                "Before submitting a script for human approval, run "
                "`zaojing_audit_drama_script` and revise missing episodes, "
                "scene headings, dialogue formatting or placeholders.\n"
                "5. Structure every episode with `zaojing_plan_drama_episodes`, "
                "including time, locations, interior/exterior, characters, "
                "scenes, story beats, visual and dialogue checks, and risks. "
                "Provide sceneContracts with entering value, objectives, "
                "obstacle, tactics, beats, turn, exit value, subtext, "
                "performance and visual/sound strategy.\n"
                "6. Create scene/shot plans only for an empty episode with "
                "`zaojing_plan_drama_shots`; never overwrite existing user "
                "breakdown work.\n"
                "7. Plan reusable assets with `zaojing_plan_drama_assets`. "
                "Characters use one 16:9 character_sheet. Locations need master, "
                "interior/exterior and lighting references. Character profile "
                "must cover want, need, wound, false belief, fear, contradiction, "
                "public/private self, speech, voice, body, arc and continuity.\n"
                "8. Review each stage through the responsible roles and record "
                "findings with `zaojing_review_drama_stage`. Agent review is "
                "evidence only; the user still confirms the stage gate.\n"
                "9. Generate missing keyframes or clips with discovered models. "
                "Use first/last frames, nine-grid and storyboard references "
                "when they improve continuity.\n"
                "Bind every generated result to its semantic slot with "
                "`zaojing_bind_drama_asset`: entity assets use `primary`, "
                "`reference` or professional view keys; shots use `first_frame`, "
                "`last_frame`, `grid9`, `storyboard`, `video` or `audio`.\n"
                "When the user refines a shot prompt, persist it with "
                "`zaojing_update_drama_shot_prompt`; batch planning and single "
                "shot generation must reuse that saved prompt.\n"
                "Persist structured directing notes with "
                "`zaojing_update_drama_shot_direction`, including scale, angle, "
                "movement, lens, blocking, performance, composition, lighting, "
                "sound and transition. Scene contracts and shot direction must "
                "be injected into keyframe, storyboard and clip prompts.\n"
                "Persist reusable character, location, costume, prop and style "
                "slot prompts with `zaojing_update_drama_entity_prompt` before "
                "batch asset generation.\n"
                "When several assets or shots need the same stage of work, "
                "prefer `zaojing_plan_drama_production_run`. It reads the "
                "episode, missing slots, model defaults and reference assets "
                "to create a review-only task graph. Present item count, "
                "skipped items and models before starting the run.\n"
                "Inspect alternatives with "
                "`zaojing_list_drama_asset_candidates` and select or reject "
                "with `zaojing_update_drama_asset_candidate`.\n"
                "Approve individual shot clips only after their video exists; "
                "use `zaojing_set_drama_shot_status`. Replacing the video "
                "automatically returns the shot to clip_ready for review. Use "
                "`zaojing_get_drama_shot_history` when review provenance matters.\n"
                "Any script, asset, shot, direction, prompt or timeline mutation starts "
                "a new stage revision and invalidates older role reviews and "
                "user approvals. Rerun the relevant audit before asking for "
                "approval again.\n"
                "10. Respect each character's voiceName and voiceRate when "
                "using `zaojing_synthesize_speech`.\n"
                "11. Use `zaojing_process_media` for audio extraction, -16 LUFS "
                "normalization, subtitle transcription or upscale.\n"
                "12. Run `zaojing_audit_drama_project` before expensive "
                "rendering, then check subtitles, audio mix and every clip.\n"
                "13. Render only through `zaojing_render_episode` and report the "
                "durable export asset ID. Use "
                "`zaojing_list_drama_export_manifests` when lineage or a "
                "previous render's exact inputs must be reviewed. Final render "
                "requires every shot to be approved; strictApprovals=false is "
                "only for an explicitly requested preview.\n"
                "\n"
                "If a clip mixes dialogue with music or ambience, use an "
                "`audio_processing` separation model and bind the vocals stem "
                "only when it is the intended dialogue track.\n"
                "Use `transcribe_audio` to create subtitle cues from the chosen "
                "dialogue track, then review timing and text before episode render.\n"
            ),
        )
        self._sync_shared_file(
            self.shared_root / "tools" / "media-tools.md",
            (
                "# Media Tools\n\n"
                "- `zaojing_discover_media_models`\n"
                "- `zaojing_list_media_assets`\n"
                "- `zaojing_generate_media`\n"
                "- `zaojing_get_media_task`\n"
                "- `zaojing_retry_media_tasks`\n"
                "- `zaojing_list_speech_voices`\n"
                "- `zaojing_synthesize_speech`\n"
                "- `zaojing_process_media`\n"
                "- `zaojing_list_drama_projects`\n"
                "- `zaojing_get_drama_production`\n"
                "- `zaojing_get_drama_episode`\n"
                "- `zaojing_audit_drama_episode`\n"
                "- `zaojing_get_drama_roles`\n"
                "- `zaojing_get_drama_control_room`\n"
                "- `zaojing_audit_drama_script`\n"
                "- `zaojing_save_drama_draft`\n"
                "- `zaojing_plan_drama_episodes`\n"
                "- `zaojing_plan_drama_shots`\n"
                "- `zaojing_plan_drama_assets`\n"
                "- `zaojing_bind_drama_asset`\n"
                "- `zaojing_update_drama_shot_prompt`\n"
                "- `zaojing_update_drama_shot_direction`\n"
                "- `zaojing_update_drama_entity_prompt`\n"
                "- `zaojing_set_drama_shot_status`\n"
                "- `zaojing_get_drama_shot_history`\n"
                "- `zaojing_list_drama_asset_candidates`\n"
                "- `zaojing_update_drama_asset_candidate`\n"
                "- `zaojing_list_drama_production_runs`\n"
                "- `zaojing_create_drama_production_run`\n"
                "- `zaojing_plan_drama_production_run`\n"
                "- `zaojing_get_drama_production_run`\n"
                "- `zaojing_start_drama_production_run`\n"
                "- `zaojing_retry_drama_production_failures`\n"
                "- `zaojing_cancel_drama_production_run`\n"
                "- `zaojing_review_drama_stage`\n"
                "- `zaojing_audit_drama_project`\n"
                "- `zaojing_render_episode`\n"
                "- `zaojing_list_drama_export_manifests`\n"
            ),
        )

    def ensure(self, conversation_id: str) -> Path:
        self.initialize()
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", conversation_id)
        workspace = (self.sessions_root / safe_id).resolve()
        if self.sessions_root.resolve() not in workspace.parents:
            raise ValueError("会话 workspace 路径非法")
        workspace.mkdir(parents=True, exist_ok=True)
        self._write_once(
            workspace / "README.md",
            (
                "# Conversation Workspace\n\n"
                f"Conversation: `{conversation_id}`\n\n"
                "This directory belongs only to this conversation. Shared "
                "playbooks live in the sibling `shared` directory and are "
                "read-only.\n"
            ),
        )
        return workspace

    @staticmethod
    def _write_once(path: Path, content: str) -> None:
        if path.exists():
            return
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _sync_shared_file(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        path.write_text(content, encoding="utf-8")
