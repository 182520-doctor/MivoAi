"""Dynamic Agent tools for creative and media workflows."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from app.modules.assets import AssetService
from app.modules.drama import DramaProjectService
from app.modules.media_generation import (
    CreateGenerationCommand,
    GenerationService,
)
from app.modules.media_processing import MediaProcessingService
from app.modules.providers import ProviderService
from app.shared.errors import ProviderConfigurationError


def media_dynamic_tool_specs() -> list[dict[str, Any]]:
    """Return the tools exposed to every new Codex creative thread."""

    return [
        {
            "type": "function",
            "name": "zaojing_get_shared_context",
            "description": (
                "Read shared Zaojing tools documentation and playbooks. Use the "
                "returned guidance before planning complex creative work."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional relative path such as "
                            "playbooks/multimodal.md. Omit to list all playbooks."
                        ),
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_discover_media_models",
            "description": (
                "Discover enabled Zaojing media models and their canonical input "
                "schemas. Call this before generating so you can choose the model "
                "that matches the user's requested modality and references."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "enum": [
                            "image_generation",
                            "image_processing",
                            "video_generation",
                            "video_processing",
                            "audio_processing",
                            "transcription",
                        ],
                        "description": "Optional capability filter.",
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_media_assets",
            "description": (
                "List uploaded or generated assets. Use asset IDs when a selected "
                "model accepts image, video, audio, or file references."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["image", "video", "audio", "file"],
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_generate_media",
            "description": (
                "Submit a durable image, video or audio processing task using a model "
                "returned by zaojing_discover_media_models. Reference asset IDs are "
                "passed as modality arrays; never pass ComfyUI node IDs. The tool "
                "waits briefly and returns a task ID plus any completed results."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "providerId": {"type": "string"},
                    "modelId": {"type": "string"},
                    "taskType": {
                        "type": "string",
                        "enum": [
                            "image_generation",
                            "image_processing",
                            "video_generation",
                            "video_processing",
                            "audio_processing",
                            "transcription",
                        ],
                    },
                    "prompt": {"type": "string"},
                    "images": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "videos": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "audios": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "parameters": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                    "waitSeconds": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 60,
                    },
                },
                "required": ["providerId", "modelId", "taskType"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_media_task",
            "description": (
                "Query a generation task by task ID. Set waitSeconds to wait for "
                "updates. Completed tasks include result asset IDs and local URLs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "taskId": {"type": "string"},
                    "waitSeconds": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 120,
                    },
                },
                "required": ["taskId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_retry_media_tasks",
            "description": (
                "Retry failed or canceled media tasks from their persisted "
                "canonical request. Up to 50 task IDs can be retried in one "
                "explicit user-approved batch. Running and succeeded tasks are "
                "never retried."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "taskIds": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 50,
                        "items": {"type": "string"},
                    }
                },
                "required": ["taskIds"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_speech_voices",
            "description": (
                "List voices available from the local offline speech engine."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_synthesize_speech",
            "description": (
                "Generate an offline speech audio asset. When shotId is supplied, "
                "the resulting audioAssetId is bound to that shot."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "voiceName": {"type": "string"},
                    "rate": {
                        "type": "integer",
                        "minimum": -10,
                        "maximum": 10,
                    },
                    "shotId": {"type": "string"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_process_media",
            "description": (
                "Run deterministic media preparation. Use extract_audio for a "
                "video, or upscale_video to produce a 1080p project-ratio clip. "
                "Use normalize_audio to apply EBU R128 loudness normalization to "
                "an audio asset. Use transcribe_audio to produce timestamped "
                "subtitle cues from audio. "
                "When shotId is supplied, attach the processed asset to the shot."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "extract_audio",
                            "upscale_video",
                            "normalize_audio",
                            "transcribe_audio",
                        ],
                    },
                    "videoAssetId": {"type": "string"},
                    "assetId": {"type": "string"},
                    "aspectRatio": {"type": "string"},
                    "targetLufs": {
                        "type": "number",
                        "minimum": -24,
                        "maximum": -9,
                    },
                    "truePeakDb": {
                        "type": "number",
                        "minimum": -6,
                        "maximum": -0.1,
                    },
                    "loudnessRange": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 30,
                    },
                    "language": {"type": "string"},
                    "shotId": {"type": "string"},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_drama_projects",
            "description": "List local short-drama projects and their current stages.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_production",
            "description": (
                "Read episodes, scenes and shots for a short-drama project, "
                "including clip, audio, subtitle and render state."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_series",
            "description": (
                "Read a project-level multi-episode production overview. "
                "Returns per-episode plan, keyframe, video, approval and "
                "render coverage plus the next required production action."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_episode",
            "description": (
                "Read exactly one episode's persisted plan, scenes, shots, "
                "assets references and completion state. Prefer this over "
                "loading every episode when working inside one episode thread."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "episodeId": {"type": "string"},
                },
                "required": ["episodeId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_audit_drama_episode",
            "description": (
                "Run deterministic checks for one episode's structured plan, "
                "scene headings, shot descriptions, duration, dialogue and "
                "asset references. Use the returned gap list to revise drafts "
                "and audit again before asking the user to approve the stage."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "episodeId": {"type": "string"},
                },
                "required": ["episodeId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_roles",
            "description": (
                "Read the professional short-drama role handbook. Each role "
                "contains responsibilities, required inputs, deliverables, "
                "checklists and review criteria. Use it before drafting or "
                "reviewing a stage."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "enum": [
                            "brief",
                            "bible",
                            "script",
                            "breakdown",
                            "assets",
                            "keyframes",
                            "clips",
                            "timeline",
                        ],
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_control_room",
            "description": (
                "Read the current stage gates, role review results, user "
                "decisions and structured episode plans for a drama project."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_audit_drama_script",
            "description": (
                "Run deterministic checks on the latest drama script: missing "
                "or empty script, episode/scene headings, dialogue formatting, "
                "duplicate episode numbers, placeholder text, actionless "
                "dialogue scenes, overwritten speeches and long dialogue runs. "
                "Use the returned sceneCraft signals together with the "
                "professional story playbook, revise the draft yourself, and "
                "re-run before requesting user approval."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_save_drama_draft",
            "description": (
                "Save an Agent-authored draft for the brief, story bible or "
                "script. This creates a reviewable document version and never "
                "marks it user-approved."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["brief", "story_bible", "script"],
                    },
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["projectId", "kind", "content"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_plan_drama_episodes",
            "description": (
                "Create or update structured episode plans. Each episode must "
                "cover timeScope, locations, interiorExterior, characters, "
                "scenes, storyBeats, visualRequirements, dialogueRequirements "
                "and continuityRisks. Use sceneContracts to record each "
                "scene's value change, objectives, obstacle, tactics, turn, "
                "subtext, performance and visual strategy. Existing user plans are updated only "
                "when episodeId is supplied."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "episodes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "episodeId": {"type": "string"},
                                "title": {"type": "string"},
                                "synopsis": {"type": "string"},
                                "timeScope": {"type": "string"},
                                "locations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "interiorExterior": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "characters": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "scenes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "storyBeats": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "visualRequirements": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "dialogueRequirements": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "continuityRisks": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "sceneContracts": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "sceneNumber": {
                                                "type": "integer",
                                                "minimum": 1,
                                            },
                                            "title": {"type": "string"},
                                            "valueIn": {"type": "string"},
                                            "characterObjectives": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "obstacle": {"type": "string"},
                                            "tactics": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "beats": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "turn": {"type": "string"},
                                            "valueOut": {"type": "string"},
                                            "subtext": {"type": "string"},
                                            "visualStrategy": {
                                                "type": "string"
                                            },
                                            "performanceNotes": {
                                                "type": "string"
                                            },
                                            "soundNotes": {
                                                "type": "string"
                                            },
                                        },
                                        "required": [
                                            "sceneNumber",
                                            "valueIn",
                                            "characterObjectives",
                                            "obstacle",
                                            "turn",
                                            "valueOut",
                                        ],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["timeScope", "locations", "scenes"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["projectId", "episodes"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_plan_drama_shots",
            "description": (
                "Create scenes and shots for an episode whose scene list is "
                "still empty. This tool refuses to overwrite existing user "
                "breakdown work."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "episodeId": {"type": "string"},
                    "scenes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "summary": {"type": "string"},
                                "scriptDocumentId": {"type": "string"},
                                "shots": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "description": {"type": "string"},
                                            "dialogue": {"type": "string"},
                                            "durationSeconds": {
                                                "type": "number",
                                                "minimum": 0.1,
                                                "maximum": 3600,
                                            },
                                            "direction": {
                                                "type": "object",
                                                "properties": {
                                                    "shotSize": {
                                                        "type": "string"
                                                    },
                                                    "cameraAngle": {
                                                        "type": "string"
                                                    },
                                                    "cameraMovement": {
                                                        "type": "string"
                                                    },
                                                    "lens": {
                                                        "type": "string"
                                                    },
                                                    "blocking": {
                                                        "type": "string"
                                                    },
                                                    "performanceAction": {
                                                        "type": "string"
                                                    },
                                                    "expression": {
                                                        "type": "string"
                                                    },
                                                    "composition": {
                                                        "type": "string"
                                                    },
                                                    "lighting": {
                                                        "type": "string"
                                                    },
                                                    "sound": {
                                                        "type": "string"
                                                    },
                                                    "transition": {
                                                        "type": "string"
                                                    },
                                                    "referenceNotes": {
                                                        "type": "string"
                                                    },
                                                },
                                                "additionalProperties": False,
                                            },
                                        },
                                        "required": ["title", "description"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["heading", "shots"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["episodeId", "scenes"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_plan_drama_assets",
            "description": (
                "Create or update the asset requirements for characters, "
                "locations, costumes, props and style references. assetSlots "
                "use stable keys such as character_sheet, interior, exterior, "
                "master, fabric_detail and moodboard. A character uses one "
                "16:9 character_sheet containing a head close-up, full front/"
                "side/back views, expression close-up and costume detail."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "entities": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "character",
                                        "costume",
                                        "prop",
                                        "location",
                                        "style",
                                    ],
                                },
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "profile": {
                                    "type": "object",
                                    "properties": {
                                        "want": {"type": "string"},
                                        "need": {"type": "string"},
                                        "wound": {"type": "string"},
                                        "falseBelief": {"type": "string"},
                                        "fear": {"type": "string"},
                                        "contradiction": {"type": "string"},
                                        "publicMask": {"type": "string"},
                                        "privateSelf": {"type": "string"},
                                        "speechPattern": {"type": "string"},
                                        "voiceNotes": {"type": "string"},
                                        "bodyBehavior": {"type": "string"},
                                        "arcStart": {"type": "string"},
                                        "arcEnd": {"type": "string"},
                                        "relationships": {"type": "string"},
                                        "continuityRules": {"type": "string"},
                                    },
                                    "additionalProperties": False,
                                },
                                "assetSlots": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "string"
                                    },
                                },
                            },
                            "required": ["kind", "name"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["projectId", "entities"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_bind_drama_asset",
            "description": (
                "Bind a generated or uploaded asset to a semantic drama slot. "
                "Entity slots accept image assets. Shot slots are first_frame, "
                "last_frame, grid9 and storyboard for images, video for a clip, "
                "and audio for a dialogue or sound track. This is how generated "
                "media re-enters the persisted production graph."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "targetType": {
                        "type": "string",
                        "enum": ["entity", "shot"],
                    },
                    "targetId": {"type": "string"},
                    "slot": {
                        "type": "string",
                        "enum": [
                            "primary",
                            "reference",
                            "character_sheet",
                            "turnaround_front",
                            "turnaround_three_quarter",
                            "turnaround_side",
                            "turnaround_back",
                            "expression_sheet",
                            "costume_detail",
                            "master",
                            "interior",
                            "exterior",
                            "lighting_reference",
                            "front",
                            "back",
                            "fabric_detail",
                            "hero",
                            "scale_reference",
                            "moodboard",
                            "first_frame",
                            "last_frame",
                            "grid9",
                            "storyboard",
                            "video",
                            "audio",
                        ],
                    },
                    "assetId": {"type": "string"},
                },
                "required": ["targetType", "targetId", "slot", "assetId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_update_drama_shot_prompt",
            "description": (
                "Save a durable prompt override for one shot slot. Batch run "
                "planning and manual generation both prefer this saved text "
                "over the automatically derived prompt."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shotId": {"type": "string"},
                    "slot": {
                        "type": "string",
                        "enum": [
                            "first_frame",
                            "last_frame",
                            "grid9",
                            "storyboard",
                            "video",
                            "audio",
                        ],
                    },
                    "prompt": {"type": "string", "maxLength": 12000},
                },
                "required": ["shotId", "slot", "prompt"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_update_drama_shot_direction",
            "description": (
                "Persist structured directing notes for one shot: scale, angle, "
                "camera movement, lens, blocking, performance, expression, "
                "composition, lighting, sound, transition and reference notes. "
                "Updating the design invalidates prior shot approval and feeds "
                "keyframe and video generation."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shotId": {"type": "string"},
                    "direction": {
                        "type": "object",
                        "properties": {
                            "shotSize": {"type": "string"},
                            "cameraAngle": {"type": "string"},
                            "cameraMovement": {"type": "string"},
                            "lens": {"type": "string"},
                            "blocking": {"type": "string"},
                            "performanceAction": {"type": "string"},
                            "expression": {"type": "string"},
                            "composition": {"type": "string"},
                            "lighting": {"type": "string"},
                            "sound": {"type": "string"},
                            "transition": {"type": "string"},
                            "referenceNotes": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["shotId", "direction"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_update_drama_entity_prompt",
            "description": (
                "Save a durable prompt override for one reusable entity asset "
                "slot such as a character turnaround, expression sheet or empty "
                "scene plate. Batch asset planning reuses the saved prompt."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entityId": {"type": "string"},
                    "slot": {"type": "string"},
                    "prompt": {"type": "string", "maxLength": 12000},
                },
                "required": ["entityId", "slot", "prompt"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_set_drama_shot_status",
            "description": (
                "Approve a shot only after its video exists, or return it to "
                "clip_ready for revision. A new or replaced video automatically "
                "returns to clip_ready."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shotId": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "planned",
                            "keyframe_ready",
                            "clip_ready",
                            "approved",
                        ],
                    },
                    "note": {"type": "string", "maxLength": 2000},
                },
                "required": ["shotId", "status"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_shot_history",
            "description": (
                "Read the immutable status history for one shot, including "
                "approval, return-for-revision and automatic replacement events."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shotId": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["shotId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_drama_asset_candidates",
            "description": (
                "List persisted candidate media for a drama project. Use this "
                "before choosing or rejecting a generated keyframe, storyboard, "
                "clip or reusable entity asset. Candidates remain available "
                "after replacing the current slot asset."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "subjectType": {
                        "type": "string",
                        "enum": ["entity", "shot"],
                    },
                    "subjectId": {"type": "string"},
                    "slot": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_update_drama_asset_candidate",
            "description": (
                "Select, restore or reject one persisted drama asset candidate. "
                "Selecting a candidate also updates the semantic slot. A selected "
                "slot asset cannot be rejected until another candidate is chosen."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "candidateId": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["candidate", "selected", "rejected"],
                    },
                },
                "required": ["candidateId", "status"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_drama_production_runs",
            "description": (
                "List persisted batch production runs for a drama project, "
                "optionally filtered to one episode."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "episodeId": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_create_drama_production_run",
            "description": (
                "Create a durable batch production run for one episode. Each "
                "item targets an entity or shot semantic slot and carries a "
                "complete provider-neutral media request. This only plans the "
                "run; it does not spend GPU until the user approves start."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "episodeId": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": ["assets", "keyframes", "clips"],
                    },
                    "name": {"type": "string"},
                    "requiresApproval": {"type": "boolean"},
                    "maxParallel": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                    },
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 100,
                        "items": {
                            "type": "object",
                            "properties": {
                                "targetType": {
                                    "type": "string",
                                    "enum": ["entity", "shot"],
                                },
                                "targetId": {"type": "string"},
                                "slot": {"type": "string"},
                                "title": {"type": "string"},
                                "request": {
                                    "type": "object",
                                    "properties": {
                                        "providerId": {"type": "string"},
                                        "modelId": {"type": "string"},
                                        "taskType": {
                                            "type": "string",
                                            "enum": [
                                                "image_generation",
                                                "video_generation",
                                                "audio_processing",
                                            ],
                                        },
                                        "prompt": {"type": "string"},
                                        "images": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "videos": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "audios": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "files": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "parameters": {"type": "object"},
                                    },
                                    "required": [
                                        "providerId",
                                        "modelId",
                                        "taskType",
                                        "prompt",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                            "required": [
                                "targetType",
                                "targetId",
                                "slot",
                                "request",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "projectId",
                    "episodeId",
                    "stage",
                    "items",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_plan_drama_production_run",
            "description": (
                "Automatically assemble a reviewable batch run from one "
                "episode's current shots, entity references and missing slots. "
                "The planner applies model defaults and limits, builds "
                "provider-neutral requests, and does not start GPU work."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "episodeId": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": ["assets", "keyframes", "clips"],
                    },
                    "providerId": {"type": "string"},
                    "modelId": {"type": "string"},
                    "slots": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "targetIds": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "parameters": {"type": "object"},
                    "promptPrefix": {"type": "string"},
                    "onlyMissing": {"type": "boolean"},
                    "requiresApproval": {"type": "boolean"},
                    "maxParallel": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                    },
                    "name": {"type": "string"},
                },
                "required": [
                    "projectId",
                    "episodeId",
                    "stage",
                    "providerId",
                    "modelId",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_get_drama_production_run",
            "description": (
                "Read one batch run with item status, media task IDs, result "
                "assets and failures. Use this to report progress or decide "
                "which failed items need retry."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"runId": {"type": "string"}},
                "required": ["runId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_start_drama_production_run",
            "description": (
                "Start a planned batch run after explicit user confirmation of "
                "scope, model, item count and GPU cost. Already-running or "
                "finished runs are returned without resubmission."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runId": {"type": "string"},
                    "approvedBy": {"type": "string"},
                },
                "required": ["runId", "approvedBy"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_retry_drama_production_failures",
            "description": (
                "Retry only failed items in a partial, failed or canceled batch "
                "run. Successful items and their bound assets remain untouched."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runId": {"type": "string"},
                    "approvedBy": {"type": "string"},
                },
                "required": ["runId", "approvedBy"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_cancel_drama_production_run",
            "description": (
                "Cancel a queued or running batch after the current media "
                "request. Completed items remain persisted."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"runId": {"type": "string"}},
                "required": ["runId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_review_drama_stage",
            "description": (
                "Record an Agent review for one production role and stage. A "
                "pass from the Agent is evidence only; the user still decides "
                "whether the gate is approved. Use changes_requested with "
                "specific feedback when issues remain."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "enum": [
                            "brief",
                            "bible",
                            "script",
                            "breakdown",
                            "assets",
                            "keyframes",
                            "clips",
                            "timeline",
                        ],
                    },
                    "roleId": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "passed",
                            "changes_requested",
                            "failed",
                        ],
                    },
                    "score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "checklist": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "label": {"type": "string"},
                                "passed": {"type": "boolean"},
                                "note": {"type": "string"},
                            },
                            "required": ["key", "label", "passed"],
                            "additionalProperties": False,
                        },
                    },
                    "feedback": {"type": "string"},
                },
                "required": [
                    "projectId",
                    "stage",
                    "roleId",
                    "status",
                    "score",
                    "checklist",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_audit_drama_project",
            "description": (
                "Run deterministic continuity checks for locked assets, missing "
                "clips/audio, shot entity references, character voices and "
                "subtitles."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "projectId": {"type": "string"},
                },
                "required": ["projectId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_render_episode",
            "description": (
                "Render an episode using current shot videos, audio, subtitles and "
                "mix settings. Supports none or crossfade transitions."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "episodeId": {"type": "string"},
                    "transition": {
                        "type": "string",
                        "enum": ["none", "crossfade"],
                    },
                    "transitionDuration": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 3,
                    },
                    "strictApprovals": {
                        "type": "boolean",
                        "description": (
                            "Defaults to true. False is a preview-only render "
                            "and must be explicitly requested by the user."
                        ),
                    },
                },
                "required": ["episodeId"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "zaojing_list_drama_export_manifests",
            "description": (
                "Read immutable export manifests for an episode. Each manifest "
                "records the exact stage revisions, documents, entity slots, "
                "shot media, subtitles, audio mix and approval warnings used by "
                "that render."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"episodeId": {"type": "string"}},
                "required": ["episodeId"],
                "additionalProperties": False,
            },
        },
    ]


class AgentMediaToolService:
    """Execute model-selected media tools against application use cases."""

    def __init__(
        self,
        providers: ProviderService,
        generation: GenerationService,
        assets: AssetService,
        shared_root: Path | None = None,
        media_processing: MediaProcessingService | None = None,
        drama: DramaProjectService | None = None,
    ) -> None:
        self._providers = providers
        self._generation = generation
        self._assets = assets
        self._shared_root = shared_root.resolve() if shared_root else None
        self._media_processing = media_processing
        self._drama = drama

    async def handle(
        self,
        tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            if tool == "zaojing_discover_media_models":
                return self._result(self._discover(arguments))
            if tool == "zaojing_get_shared_context":
                return self._result(self._shared_context(arguments))
            if tool == "zaojing_list_media_assets":
                return self._result(self._list_assets(arguments))
            if tool == "zaojing_generate_media":
                return await self._generate(arguments)
            if tool == "zaojing_get_media_task":
                return await self._get_task(arguments)
            if tool == "zaojing_retry_media_tasks":
                return self._result(
                    await self._generation.retry_many(
                        [
                            str(task_id)
                            for task_id in arguments.get("taskIds") or []
                        ]
                    )
                )
            if tool == "zaojing_list_speech_voices":
                return self._result({"voices": self._require_media().speech_voices()})
            if tool == "zaojing_synthesize_speech":
                return self._synthesize_speech(arguments)
            if tool == "zaojing_process_media":
                return self._process_media(arguments)
            if tool == "zaojing_list_drama_projects":
                return self._result(
                    {
                        "projects": self._require_drama().list_projects(
                            int(arguments.get("limit") or 100)
                        )
                    }
                )
            if tool == "zaojing_get_drama_production":
                return self._result(
                    {
                        "production": self._require_drama().production(
                            str(arguments["projectId"])
                        )
                    }
                )
            if tool == "zaojing_get_drama_series":
                return self._result(
                    {
                        "series": self._require_drama().series_production(
                            str(arguments["projectId"])
                        )
                    }
                )
            if tool == "zaojing_get_drama_episode":
                return self._result(
                    {
                        "episode": self._require_drama().episode_production(
                            str(arguments["episodeId"])
                        )
                    }
                )
            if tool == "zaojing_audit_drama_episode":
                return self._result(
                    {
                        "audit": self._require_drama().audit_episode(
                            str(arguments["episodeId"])
                        )
                    }
                )
            if tool == "zaojing_get_drama_roles":
                return self._result(
                    {
                        "roles": self._require_drama().roles(
                            stage=str(arguments.get("stage") or "") or None
                        ),
                        "guidance": (
                            "Use the selected role's inputs, deliverables and "
                            "checklist. Ask the user to confirm creative choices "
                            "before saving or rendering."
                        ),
                    }
                )
            if tool == "zaojing_get_drama_control_room":
                return self._result(
                    {
                        "controlRoom": self._require_drama().production_control(
                            str(arguments["projectId"])
                        )
                    }
                )
            if tool == "zaojing_audit_drama_script":
                return self._result(
                    {
                        "audit": self._require_drama().audit_script(
                            str(arguments["projectId"])
                        )
                    }
                )
            if tool == "zaojing_save_drama_draft":
                return self._result(
                    {
                        "document": self._require_drama().create_document(
                            str(arguments["projectId"]),
                            kind=str(arguments["kind"]),
                            title=str(arguments.get("title") or ""),
                            content=str(arguments["content"]),
                        )
                    }
                )
            if tool == "zaojing_plan_drama_episodes":
                return self._result(
                    {
                        "episodes": self._require_drama().plan_episodes(
                            str(arguments["projectId"]),
                            list(arguments.get("episodes") or []),
                        )
                    }
                )
            if tool == "zaojing_plan_drama_shots":
                return self._result(
                    {
                        "shotPlan": self._require_drama().plan_episode_shots(
                            str(arguments["episodeId"]),
                            list(arguments.get("scenes") or []),
                        )
                    }
                )
            if tool == "zaojing_plan_drama_assets":
                return self._result(
                    {
                        "entities": self._require_drama().plan_assets(
                            str(arguments["projectId"]),
                            list(arguments.get("entities") or []),
                        )
                    }
                )
            if tool == "zaojing_bind_drama_asset":
                target_type = str(arguments["targetType"])
                slot = str(arguments["slot"])
                target_id = str(arguments["targetId"])
                asset_id = str(arguments["assetId"])
                if target_type == "entity":
                    bound = self._require_drama().bind_entity_asset(
                        target_id,
                        slot=slot,
                        asset_id=asset_id,
                    )
                elif target_type == "shot":
                    bound = self._require_drama().bind_shot_asset(
                        target_id,
                        slot=slot,
                        asset_id=asset_id,
                    )
                else:
                    return self._failure(
                        "targetType 必须是 entity 或 shot"
                    )
                return self._result(
                    {
                        "targetType": target_type,
                        "bound": bound,
                    }
                )
            if tool == "zaojing_update_drama_shot_prompt":
                shot = self._require_drama().update_shot_prompt(
                    str(arguments["shotId"]),
                    slot=str(arguments["slot"]),
                    prompt=str(arguments["prompt"]),
                )
                if not shot:
                    return self._failure("短剧镜头不存在")
                return self._result({"shot": shot})
            if tool == "zaojing_update_drama_shot_direction":
                shot = self._require_drama().update_shot_direction(
                    str(arguments["shotId"]),
                    direction=dict(arguments.get("direction") or {}),
                )
                if not shot:
                    return self._failure("短剧镜头不存在")
                return self._result({"shot": shot})
            if tool == "zaojing_update_drama_entity_prompt":
                entity = self._require_drama().update_entity_prompt(
                    str(arguments["entityId"]),
                    slot=str(arguments["slot"]),
                    prompt=str(arguments["prompt"]),
                )
                if not entity:
                    return self._failure("短剧实体不存在")
                return self._result({"entity": entity})
            if tool == "zaojing_set_drama_shot_status":
                shot = self._require_drama().update_shot_status(
                    str(arguments["shotId"]),
                    status=str(arguments["status"]),
                    reviewer="agent",
                    note=str(arguments.get("note") or ""),
                )
                if not shot:
                    return self._failure("短剧镜头不存在")
                return self._result({"shot": shot})
            if tool == "zaojing_get_drama_shot_history":
                events = self._require_drama().shot_status_history(
                    str(arguments["shotId"]),
                    limit=int(arguments.get("limit") or 50),
                )
                if events is None:
                    return self._failure("短剧镜头不存在")
                return self._result({"events": events})
            if tool == "zaojing_list_drama_asset_candidates":
                return self._result(
                    {
                        "candidates": self._require_drama().list_asset_candidates(
                            str(arguments["projectId"]),
                            subject_type=(
                                str(arguments["subjectType"])
                                if arguments.get("subjectType")
                                else None
                            ),
                            subject_id=(
                                str(arguments["subjectId"])
                                if arguments.get("subjectId")
                                else None
                            ),
                            slot=(
                                str(arguments["slot"])
                                if arguments.get("slot")
                                else None
                            ),
                        )
                    }
                )
            if tool == "zaojing_update_drama_asset_candidate":
                return self._result(
                    {
                        "candidate": (
                            self._require_drama().update_asset_candidate_status(
                                str(arguments["candidateId"]),
                                status=str(arguments["status"]),
                            )
                        )
                    }
                )
            if tool == "zaojing_list_drama_production_runs":
                return self._result(
                    {
                        "runs": self._require_drama().list_production_runs(
                            str(arguments["projectId"]),
                            episode_id=(
                                str(arguments["episodeId"])
                                if arguments.get("episodeId")
                                else None
                            ),
                            limit=int(arguments.get("limit") or 50),
                        )
                    }
                )
            if tool == "zaojing_create_drama_production_run":
                return self._result(
                    {
                        "run": self._require_drama().create_production_run(
                            str(arguments["projectId"]),
                            episode_id=str(arguments["episodeId"]),
                            stage=str(arguments["stage"]),
                            name=str(arguments.get("name") or ""),
                            requires_approval=bool(
                                arguments.get("requiresApproval", True)
                            ),
                            max_parallel=int(
                                arguments.get("maxParallel") or 1
                            ),
                            items=list(arguments.get("items") or []),
                        )
                    }
                )
            if tool == "zaojing_plan_drama_production_run":
                return self._plan_drama_production_run(arguments)
            if tool == "zaojing_get_drama_production_run":
                return self._result(
                    {
                        "run": self._require_drama().get_production_run(
                            str(arguments["runId"])
                        )
                    }
                )
            if tool == "zaojing_start_drama_production_run":
                return self._result(
                    {
                        "run": self._require_drama().start_production_run(
                            str(arguments["runId"]),
                            approved_by=str(arguments["approvedBy"]),
                        )
                    }
                )
            if tool == "zaojing_retry_drama_production_failures":
                return self._result(
                    {
                        "run": (
                            self._require_drama().retry_failed_production_run(
                                str(arguments["runId"]),
                                approved_by=str(arguments["approvedBy"]),
                            )
                        )
                    }
                )
            if tool == "zaojing_cancel_drama_production_run":
                return self._result(
                    {
                        "run": self._require_drama().cancel_production_run(
                            str(arguments["runId"])
                        )
                    }
                )
            if tool == "zaojing_review_drama_stage":
                return self._result(
                    {
                        "review": self._require_drama().record_review(
                            str(arguments["projectId"]),
                            stage=str(arguments["stage"]),
                            role_id=str(arguments["roleId"]),
                            status=str(arguments["status"]),
                            score=float(arguments["score"]),
                            checklist=list(arguments.get("checklist") or []),
                            feedback=str(arguments.get("feedback") or ""),
                            reviewer="agent",
                        )
                    }
                )
            if tool == "zaojing_audit_drama_project":
                return self._result(
                    {
                        "audit": self._require_drama().audit(
                            str(arguments["projectId"])
                        )
                    }
                )
            if tool == "zaojing_render_episode":
                return await self._render_episode(arguments)
            if tool == "zaojing_list_drama_export_manifests":
                return self._result(
                    {
                        "manifests": self._require_drama().export_manifests(
                            str(arguments["episodeId"])
                        )
                    }
                )
            return self._failure(f"未知工具：{tool}")
        except Exception as exc:  # noqa: BLE001 - errors are returned to the model
            return self._failure(str(exc))

    def _plan_drama_production_run(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        drama = self._require_drama()
        project_id = str(arguments["projectId"])
        episode_id = str(arguments["episodeId"])
        stage = str(arguments["stage"])
        provider_id = str(arguments["providerId"])
        model_id = str(arguments["modelId"])
        project = drama.get_project(project_id)
        if not project:
            raise ProviderConfigurationError("短剧项目不存在")
        episode = drama.episode_production(episode_id)
        if episode["projectId"] != project_id:
            raise ProviderConfigurationError("短剧分集不属于当前项目")
        model = next(
            (
                item
                for item in self._providers.list_models()
                if item["id"] == model_id
                and item["providerId"] == provider_id
            ),
            None,
        )
        if not model:
            raise ProviderConfigurationError("制作运行模型不存在")
        if not model.get("configured"):
            raise ProviderConfigurationError("制作运行模型缺少连接凭据")
        task_type = {
            "assets": "image_generation",
            "keyframes": "image_generation",
            "clips": "video_generation",
        }.get(stage)
        if not task_type:
            raise ProviderConfigurationError("未知的制作运行阶段")
        if task_type not in (model.get("capabilities") or []):
            raise ProviderConfigurationError("所选模型不支持该制作阶段")
        parameters = {
            str(parameter["key"]): parameter["default"]
            for parameter in model.get("parameters") or []
            if isinstance(parameter, dict)
            and parameter.get("key")
            and parameter.get("default") is not None
        }
        parameters.update(dict(arguments.get("parameters") or {}))
        if "aspectRatio" in parameters:
            parameters["aspectRatio"] = project["format"]
        references = {
            str(item.get("type")): item
            for item in model.get("references") or []
            if isinstance(item, dict)
        }
        image_reference = references.get("image") or {}
        image_min = int(image_reference.get("min") or 0)
        image_max = int(image_reference.get("max") or 0)
        entities = {
            entity["id"]: entity
            for entity in drama.list_entities(project_id)
        }
        target_ids = {
            str(value) for value in arguments.get("targetIds") or []
        }
        only_missing = bool(arguments.get("onlyMissing", True))
        prompt_prefix = str(arguments.get("promptPrefix") or "").strip()
        items: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []

        if stage == "assets":
            requested_slots = [
                str(value) for value in arguments.get("slots") or []
            ]
            for entity in entities.values():
                if target_ids and entity["id"] not in target_ids:
                    continue
                slots = requested_slots or _default_entity_run_slots(
                    entity["kind"]
                )
                source_images = _entity_reference_images(entity)
                input_images = (
                    source_images[:image_max] if image_max > 0 else []
                )
                for slot in slots:
                    if only_missing and _entity_slot_value(entity, slot):
                        continue
                    if slot != "primary" and not source_images:
                        skipped.append(
                            {
                                "targetId": entity["id"],
                                "reason": (
                                    f"{slot} 缺少身份基准图；"
                                    "请先生成 primary，再使用参考生图生成细节视图"
                                ),
                            }
                        )
                        continue
                    if slot != "primary" and image_max <= 0:
                        skipped.append(
                            {
                                "targetId": entity["id"],
                                "reason": (
                                    f"{slot} 需要参考主图保持身份一致，"
                                    "但所选模型不支持图片参考"
                                ),
                            }
                        )
                        continue
                    if len(input_images) < image_min:
                        skipped.append(
                            {
                                "targetId": entity["id"],
                                "reason": (
                                    f"参考图不足：需要 {image_min} 张，"
                                    f"当前 {len(input_images)} 张"
                                ),
                            }
                        )
                        continue
                    prompt = (
                        (entity.get("assetPrompts") or {}).get(slot)
                        or _entity_asset_prompt(
                            project,
                            entity,
                            slot,
                            prompt_prefix,
                        )
                    )
                    slot_parameters = dict(parameters)
                    if slot == "character_sheet":
                        slot_parameters["aspectRatio"] = "16:9"
                    items.append(
                        {
                            "targetType": "entity",
                            "targetId": entity["id"],
                            "slot": slot,
                            "title": (
                                f"{entity['name']} · "
                                f"{_entity_slot_label(slot)}"
                            ),
                            "request": {
                                "providerId": provider_id,
                                "modelId": model_id,
                                "taskType": task_type,
                                "prompt": prompt,
                                "images": input_images,
                                "videos": [],
                                "audios": [],
                                "files": [],
                                "parameters": slot_parameters,
                            },
                        }
                    )
        else:
            requested_slots = [
                str(value) for value in arguments.get("slots") or []
            ]
            if not requested_slots:
                requested_slots = (
                    ["first_frame"] if stage == "keyframes" else ["video"]
                )
            allowed_slots = (
                {"first_frame", "last_frame", "grid9", "storyboard"}
                if stage == "keyframes"
                else {"video"}
            )
            invalid_slots = set(requested_slots) - allowed_slots
            if invalid_slots:
                raise ProviderConfigurationError(
                    f"当前阶段不支持槽位：{'、'.join(sorted(invalid_slots))}"
                )
            contracts = {
                int(contract.get("sceneNumber") or 0): contract
                for contract in (episode.get("plan") or {}).get(
                    "sceneContracts"
                ) or []
            }
            for scene in episode.get("scenes") or []:
                scene_contract = contracts.get(
                    int(scene.get("sceneNumber") or 0)
                )
                for shot in scene.get("shots") or []:
                    if target_ids and shot["id"] not in target_ids:
                        continue
                    referenced = [
                        entities[reference["entityId"]]
                        for reference in shot.get("entityReferences") or []
                        if reference.get("entityId") in entities
                    ]
                    source_images = _shot_reference_images(shot, referenced)
                    input_images = (
                        source_images[:image_max] if image_max > 0 else []
                    )
                    if len(input_images) < image_min:
                        skipped.append(
                            {
                                "targetId": shot["id"],
                                "reason": (
                                    f"参考图不足：需要 {image_min} 张，"
                                    f"当前 {len(input_images)} 张"
                                ),
                            }
                        )
                        continue
                    for slot in requested_slots:
                        if only_missing and _shot_slot_value(shot, slot):
                            continue
                        slot_parameters = dict(parameters)
                        if task_type == "video_generation":
                            slot_parameters["duration"] = shot[
                                "durationSeconds"
                            ]
                            input_images = (
                                _shot_reference_images(
                                    shot,
                                    referenced,
                                    include_frames=True,
                                )[:image_max]
                                if image_max > 0
                                else []
                            )
                        prompt = (
                            (shot.get("promptOverrides") or {}).get(slot)
                            or _shot_production_prompt(
                                project,
                                shot,
                                referenced,
                                slot,
                                prompt_prefix,
                                scene_contract=scene_contract,
                            )
                        )
                        items.append(
                            {
                                "targetType": "shot",
                                "targetId": shot["id"],
                                "slot": slot,
                                "title": f"{shot['title']} · {slot}",
                                "request": {
                                    "providerId": provider_id,
                                    "modelId": model_id,
                                    "taskType": task_type,
                                    "prompt": prompt,
                                    "images": input_images,
                                    "videos": [],
                                    "audios": [],
                                    "files": [],
                                    "parameters": slot_parameters,
                                },
                            }
                        )

        if not items:
            raise ProviderConfigurationError(
                "没有可组装的制作项；请检查缺失槽位、目标过滤和参考素材"
            )
        if len(items) > 100:
            raise ProviderConfigurationError("自动任务图超过 100 项，请缩小目标范围")
        planning = {
            "source": "agent_plan",
            "skipped": skipped,
            "model": {
                "providerId": provider_id,
                "modelId": model_id,
                "name": model["name"],
                "parameters": parameters,
            },
        }
        run = drama.create_production_run(
            project_id,
            episode_id=episode_id,
            stage=stage,
            name=(
                str(arguments.get("name") or "")
                or f"{episode['title']} · {stage} 自动任务图"
            ),
            requires_approval=bool(
                arguments.get("requiresApproval", True)
            ),
            max_parallel=int(arguments.get("maxParallel") or 1),
            items=items,
            planning=planning,
        )
        return self._result(
            {
                "run": run,
                "model": {
                    "providerId": provider_id,
                    "modelId": model_id,
                    "name": model["name"],
                    "parameters": parameters,
                    "imageMinimum": image_min,
                    "imageMaximum": image_max,
                },
                "skipped": skipped,
                "guidance": (
                    "Present the item count, skipped items and model to the "
                    "user. Start only after explicit confirmation."
                ),
            }
        )

    def _discover(self, arguments: dict[str, Any]) -> dict[str, Any]:
        capability = arguments.get("capability")
        models = []
        unavailable_models = []
        for model in self._providers.list_models():
            capabilities = list(model.get("capabilities") or [])
            if capability and capability not in capabilities:
                continue
            if not any(
                item in capabilities
                for item in (
                    "image_generation",
                    "image_processing",
                    "video_generation",
                    "video_processing",
                    "audio_processing",
                    "transcription",
                )
            ):
                continue
            item = {
                "id": model["id"],
                "providerId": model["providerId"],
                "name": model["name"],
                "kind": model.get("kind"),
                "capabilities": capabilities,
                "executionMode": model.get("executionMode"),
                "parameters": model.get("parameters") or [],
                "references": model.get("references") or [],
                "configured": bool(model.get("configured")),
            }
            if not item["configured"]:
                unavailable_models.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "providerId": item["providerId"],
                        "reason": "missing_credentials",
                    }
                )
                continue
            models.append(
                {
                    "id": model["id"],
                    "providerId": model["providerId"],
                    "name": model["name"],
                    "kind": model.get("kind"),
                    "capabilities": capabilities,
                    "executionMode": model.get("executionMode"),
                    "parameters": model.get("parameters") or [],
                    "references": model.get("references") or [],
                }
            )
        return {
            "success": True,
            "models": models,
            "unavailableModels": unavailable_models,
            "guidance": (
                "Choose one model based on modality and references, then call "
                "zaojing_generate_media. Use only canonical parameter keys."
            ),
        }

    def _list_assets(self, arguments: dict[str, Any]) -> dict[str, Any]:
        library = self._assets.list(limit=int(arguments.get("limit") or 50))
        asset_type = arguments.get("type")
        assets = [
            asset
            for asset in library["assets"]
            if not asset_type or asset["type"] == asset_type
        ]
        return {"success": True, "assets": assets}

    def _shared_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._shared_root:
            return {"success": True, "files": [], "content": None}
        requested = str(arguments.get("path") or "").strip()
        if requested:
            target = (self._shared_root / requested).resolve()
            if self._shared_root not in target.parents:
                raise ValueError("共享资料路径非法")
            if not target.is_file():
                raise FileNotFoundError(requested)
            return {
                "success": True,
                "path": requested,
                "content": target.read_text(encoding="utf-8"),
            }
        files = [
            str(path.relative_to(self._shared_root)).replace("\\", "/")
            for folder in ("playbooks", "tools")
            for path in sorted((self._shared_root / folder).glob("*.md"))
        ]
        return {"success": True, "files": files}

    async def _generate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        task_type = str(arguments["taskType"])
        if task_type not in {
            "image_generation",
            "image_processing",
            "video_generation",
            "video_processing",
            "audio_processing",
            "transcription",
        }:
            return self._failure(
                "taskType 必须是 image_generation、image_processing、video_generation、"
                "video_processing、audio_processing 或 transcription"
            )
        images = [str(value) for value in arguments.get("images") or []]
        videos = [str(value) for value in arguments.get("videos") or []]
        audios = [str(value) for value in arguments.get("audios") or []]
        files = [str(value) for value in arguments.get("files") or []]
        prompt = str(arguments.get("prompt") or "")
        parameters = dict(arguments.get("parameters") or {})
        command = CreateGenerationCommand(
            provider_id=str(arguments["providerId"]),
            model_id=str(arguments["modelId"]),
            task_type=task_type,
            prompt=prompt,
            session_id=None,
            turn_id=None,
            input_asset_ids=images,
            reference_asset_ids={
                "image": images,
                "video": videos,
                "audio": audios,
                "file": files,
            },
            parameters=parameters,
            client_request_id=f"agent-{uuid.uuid4()}",
            raw_request={"agentTool": "zaojing_generate_media", **arguments},
        )
        task = await self._generation.create(command)
        task = await self._wait_for_task(
            str(task["id"]),
            int(arguments.get("waitSeconds") or 15),
        )
        return self._task_result(task)

    async def _get_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        task = await self._wait_for_task(
            str(arguments["taskId"]),
            int(arguments.get("waitSeconds") or 0),
        )
        return self._task_result(task)

    def _synthesize_speech(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = self._require_media()
        result = service.synthesize_speech(
            str(arguments["text"]),
            voice_name=str(
                arguments.get("voiceName") or "Microsoft Huihui Desktop"
            ),
            rate=int(arguments.get("rate") or 0),
            filename=f"agent-tts-{uuid.uuid4()}.wav",
        )
        shot_id = str(arguments.get("shotId") or "")
        if shot_id:
            shot = self._require_drama().update_shot(
                shot_id,
                audio_asset_id=str(result["assetId"]),
            )
            if not shot:
                return self._failure("短剧镜头不存在")
            result["shot"] = shot
        return self._result(result)

    def _process_media(self, arguments: dict[str, Any]) -> dict[str, Any]:
        service = self._require_media()
        action = str(arguments["action"])
        asset_id = str(
            arguments.get("assetId")
            or arguments.get("videoAssetId")
            or ""
        )
        if not asset_id:
            return self._failure("action 对应的 assetId 不能为空")
        if action == "extract_audio":
            result = service.extract_audio(asset_id)
        elif action == "upscale_video":
            result = service.upscale_video(
                asset_id,
                aspect_ratio=str(arguments.get("aspectRatio") or "9:16"),
            )
        elif action == "normalize_audio":
            result = service.normalize_audio(
                asset_id,
                target_lufs=float(arguments.get("targetLufs") or -16),
                true_peak_db=float(arguments.get("truePeakDb") or -1.5),
                loudness_range=float(
                    arguments.get("loudnessRange") or 11
                ),
            )
        elif action == "transcribe_audio":
            result = service.transcribe_audio(
                asset_id,
                language=str(arguments.get("language") or "auto"),
            )
        else:
            return self._failure("未知的媒体处理动作")
        shot_id = str(arguments.get("shotId") or "")
        if shot_id:
            shot = self._require_drama().update_shot(
                shot_id,
                audio_asset_id=(
                    str(result["assetId"])
                    if action
                    in {"extract_audio", "normalize_audio"}
                    else None
                ),
                video_asset_id=(
                    str(result["assetId"])
                    if action == "upscale_video"
                    else None
                ),
            )
            if not shot:
                return self._failure("短剧镜头不存在")
            result["shot"] = shot
        return self._result(result)

    async def _render_episode(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        result = await self._require_drama().render_episode(
            str(arguments["episodeId"]),
            transition=str(arguments.get("transition") or "none"),
            transition_duration=float(
                arguments.get("transitionDuration") or 0.4
            ),
            strict_approvals=bool(
                arguments.get("strictApprovals", True)
            ),
        )
        manifest = result.pop("exportManifest", None)
        if isinstance(manifest, dict):
            result["exportManifestId"] = result.get("exportManifestId")
            result["approvalComplete"] = bool(
                manifest.get("approvalComplete")
            )
            result["approvalWarnings"] = manifest.get(
                "approvalWarnings") or []
            result["manifestSummary"] = {
                "schemaVersion": manifest.get("schemaVersion"),
                "renderedAt": manifest.get("renderedAt"),
                "shotCount": len(
                    (manifest.get("rendering") or {}).get("shotOrder")
                    or []
                ),
            }
        return self._result(result)

    def _require_media(self) -> MediaProcessingService:
        if not self._media_processing:
            raise RuntimeError("媒体处理工具尚未配置")
        return self._media_processing

    def _require_drama(self) -> DramaProjectService:
        if not self._drama:
            raise RuntimeError("短剧工具尚未配置")
        return self._drama

    async def _wait_for_task(
        self,
        task_id: str,
        wait_seconds: int,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + max(
            0, min(wait_seconds, 120)
        )
        task = self._generation.get(task_id)
        while (
            task.get("status") in {"pending", "queued", "running"}
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(1)
            task = self._generation.get(task_id)
        return task

    def _task_result(self, task: dict[str, Any]) -> dict[str, Any]:
        asset_ids = [str(value) for value in task.get("resultAssetIds") or []]
        result_urls = [
            f"http://127.0.0.1:8010/api/assets/{asset_id}"
            for asset_id in asset_ids
        ]
        data = {
            **task,
            "resultUrls": result_urls,
        }
        content_items: list[dict[str, Any]] = [
            {
                "type": "inputText",
                "text": json.dumps(data, ensure_ascii=False),
            }
        ]
        return {
            "success": task.get("status") not in {"failed", "canceled"},
            "contentItems": content_items,
            "task": data,
        }

    @staticmethod
    def _result(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "contentItems": [
                {
                    "type": "inputText",
                    "text": json.dumps(data, ensure_ascii=False),
                }
            ],
            "data": data,
        }

    @staticmethod
    def _failure(message: str) -> dict[str, Any]:
        return {
            "success": False,
            "contentItems": [{"type": "inputText", "text": message}],
            "error": message,
        }


def _default_entity_run_slots(kind: str) -> list[str]:
    return {
        "character": [
            "primary",
            "character_sheet",
        ],
        "location": [
            "primary",
            "master",
            "interior",
            "exterior",
            "lighting_reference",
        ],
        "costume": ["primary", "front", "back", "fabric_detail"],
        "prop": ["primary", "hero", "scale_reference"],
        "style": ["primary", "moodboard"],
    }.get(kind, ["primary"])


def _entity_slot_label(slot: str) -> str:
    return {
        "primary": "主视觉",
        "reference": "补充参考",
        "character_sheet": "16:9 角色设定总表",
        "turnaround_front": "旧版正面视图",
        "turnaround_three_quarter": "旧版四分之三侧视图",
        "turnaround_side": "旧版侧面视图",
        "turnaround_back": "旧版背面视图",
        "expression_sheet": "旧版表情板",
        "costume_detail": "旧版服装细节板",
        "master": "总场景",
        "interior": "内景",
        "exterior": "外景",
        "lighting_reference": "灯光参考",
        "front": "服装正面",
        "back": "服装背面",
        "fabric_detail": "服装材质",
        "hero": "道具主视觉",
        "scale_reference": "道具比例",
        "moodboard": "风格板",
    }.get(slot, slot)


def _entity_slot_value(entity: dict[str, Any], slot: str) -> str | None:
    if slot == "primary":
        return entity.get("primaryAssetId")
    if slot == "reference":
        return (
            next(iter(entity.get("referenceAssetIds") or []), None)
        )
    return (entity.get("assetSlots") or {}).get(slot)


def _entity_reference_images(entity: dict[str, Any]) -> list[str]:
    values = [
        entity.get("primaryAssetId"),
        *(entity.get("referenceAssetIds") or []),
        *(entity.get("assetSlots") or {}).values(),
    ]
    return list(
        dict.fromkeys(
            str(value)
            for value in values
            if isinstance(value, str) and value
        )
    )


def _shot_slot_value(shot: dict[str, Any], slot: str) -> str | None:
    return {
        "first_frame": shot.get("firstFrameAssetId"),
        "last_frame": shot.get("lastFrameAssetId"),
        "grid9": shot.get("grid9AssetId"),
        "storyboard": shot.get("storyboardAssetId"),
        "video": shot.get("videoAssetId"),
        "audio": shot.get("audioAssetId"),
    }.get(slot)


def _shot_reference_images(
    shot: dict[str, Any],
    entities: list[dict[str, Any]],
    *,
    include_frames: bool = True,
) -> list[str]:
    values = [
        *(
            asset_id
            for entity in entities
            for asset_id in _entity_reference_images(entity)
        ),
    ]
    if include_frames:
        values.extend(
            [
                shot.get("firstFrameAssetId"),
                shot.get("lastFrameAssetId"),
                shot.get("grid9AssetId"),
                shot.get("storyboardAssetId"),
            ]
        )
    return list(
        dict.fromkeys(
            str(value)
            for value in values
            if isinstance(value, str) and value
        )
    )


def _entity_asset_prompt(
    project: dict[str, Any],
    entity: dict[str, Any],
    slot: str,
    prompt_prefix: str,
) -> str:
    slot_instruction = {
        "character_sheet": (
            "生成单张 16:9 角色设定总表。所有内容必须排在同一张连续画布内："
            "头部与面部特写；全身正面、正侧面和背面视图；表情特写；"
            "服装、纹样、发饰与材质细节特写。各视图的人物脸型、体型比例、"
            "妆发、服装左右方向和色彩必须一致，使用统一中性背景与柔光。"
            "这是一张角色设定总表，不是六张独立图片，不要输出多文件拼贴，"
            "不要添加文字、标签、字幕、水印或装饰边框。"
        ),
    }.get(
        slot,
        f"生成 {_entity_slot_label(slot)} 槽位标准参考图。",
    )
    return "\n\n".join(
        item
        for item in (
            prompt_prefix,
            (
                f"短剧《{project['title']}》的{entity['kind']}资产"
                f"“{entity['name']}”。"
            ),
            slot_instruction,
            entity.get("description") or "",
            f"全剧视觉风格：{project.get('visualStyle') or '电影写实'}。",
            (
                "保持身份、比例、服装、材质、色彩和时代设定一致；"
                "这是制作参考图，不要添加文字、字幕、水印、边框或拼贴标签。"
            ),
        )
        if item
    )


def _shot_production_prompt(
    project: dict[str, Any],
    shot: dict[str, Any],
    entities: list[dict[str, Any]],
    slot: str,
    prompt_prefix: str,
    scene_contract: dict[str, Any] | None = None,
) -> str:
    labels = {
        "first_frame": "镜头首帧",
        "last_frame": "镜头尾帧",
        "grid9": "九宫格连续帧",
        "storyboard": "电影故事板",
        "video": "镜头视频",
    }
    identity = "、".join(
        f"{entity['kind']}“{entity['name']}”" for entity in entities
    ) or "无额外角色引用"
    return "\n\n".join(
        item
        for item in (
            prompt_prefix,
            (
                f"短剧《{project['title']}》的{labels.get(slot, slot)}。"
                f"镜头标题：{shot['title']}。"
            ),
            _shot_direction_prompt(shot.get("direction") or {}),
            _scene_contract_prompt(scene_contract),
            shot.get("description") or "",
            (
                f"对白：{shot['dialogue']}"
                if shot.get("dialogue")
                else ""
            ),
            (
                f"时长：{shot['durationSeconds']} 秒；"
                f"连续性对象：{identity}。"
            ),
            f"全剧视觉风格：{project.get('visualStyle') or '电影写实'}。",
            (
                "保持人物身份、服装、场景、光源、道具和画面方向一致；"
                "不要添加未在镜头描述和对白中出现的主要人物或文字水印。"
            ),
        )
        if item
    )


def _shot_direction_prompt(direction: dict[str, Any]) -> str:
    labels = {
        "shotSize": "景别",
        "cameraAngle": "机位角度",
        "cameraMovement": "镜头运动",
        "lens": "镜头焦段",
        "blocking": "人物调度",
        "performanceAction": "表演动作",
        "expression": "表情",
        "composition": "构图",
        "lighting": "灯光",
        "sound": "声音",
        "transition": "转场",
        "referenceNotes": "参考说明",
    }
    lines = [
        f"{label}：{direction.get(key)}。"
        for key, label in labels.items()
        if isinstance(direction.get(key), str) and str(direction.get(key)).strip()
    ]
    return "".join(lines)


def _scene_contract_prompt(contract: dict[str, Any] | None) -> str:
    if not contract:
        return ""
    objectives = contract.get("characterObjectives") or []
    tactics = contract.get("tactics") or []
    beats = contract.get("beats") or []
    lines = [
        (
            "场次创作任务：从"
            f"“{contract.get('valueIn') or '起始状态'}”转向"
            f"“{contract.get('valueOut') or '结束状态'}”。"
        ),
        (
            f"人物目标：{'；'.join(str(item) for item in objectives)}。"
            if objectives
            else ""
        ),
        (
            f"障碍：{contract.get('obstacle')}。"
            if contract.get("obstacle")
            else ""
        ),
        (
            f"行动战术：{'；'.join(str(item) for item in tactics)}。"
            if tactics
            else ""
        ),
        (
            f"场次节拍：{' → '.join(str(item) for item in beats)}。"
            if beats
            else ""
        ),
        (
            f"关键转折：{contract.get('turn')}。"
            if contract.get("turn")
            else ""
        ),
        (
            f"潜台词：{contract.get('subtext')}。"
            if contract.get("subtext")
            else ""
        ),
        (
            f"声台形表：{contract.get('performanceNotes')}。"
            if contract.get("performanceNotes")
            else ""
        ),
        (
            f"视觉策略：{contract.get('visualStrategy')}。"
            if contract.get("visualStrategy")
            else ""
        ),
        (
            f"声音策略：{contract.get('soundNotes')}。"
            if contract.get("soundNotes")
            else ""
        ),
    ]
    return "".join(line for line in lines if line)
