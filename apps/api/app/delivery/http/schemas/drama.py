"""HTTP schemas for short-drama endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DramaProjectCreate(BaseModel):
    idea: str = Field(min_length=1, max_length=12000)
    title: str | None = Field(default=None, max_length=160)
    project_format: str = Field(default="9:16", alias="format", max_length=20)
    visual_style: str = Field(
        default="电影写实",
        alias="visualStyle",
        max_length=80,
    )

    model_config = {"populate_by_name": True}


class DramaProjectUpdate(BaseModel):
    active_stage: str = Field(alias="activeStage", max_length=40)
    status: str | None = Field(default=None, max_length=40)

    model_config = {"populate_by_name": True}


class DramaDocumentCreate(BaseModel):
    kind: str = Field(max_length=40)
    title: str = Field(default="", max_length=160)
    content: str = Field(default="", max_length=200000)


class DramaDocumentUpdate(BaseModel):
    title: str = Field(default="", max_length=160)
    content: str = Field(default="", max_length=200000)


class DramaEpisodeCreate(BaseModel):
    title: str = Field(default="", max_length=160)
    synopsis: str = Field(default="", max_length=4000)


class DramaSceneContractInput(BaseModel):
    scene_number: int = Field(alias="sceneNumber", ge=1, le=10000)
    title: str = Field(default="", max_length=300)
    value_in: str = Field(default="", alias="valueIn", max_length=1000)
    character_objectives: list[str] = Field(
        default_factory=list,
        alias="characterObjectives",
        max_length=50,
    )
    obstacle: str = Field(default="", max_length=2000)
    tactics: list[str] = Field(default_factory=list, max_length=50)
    beats: list[str] = Field(default_factory=list, max_length=100)
    turn: str = Field(default="", max_length=3000)
    value_out: str = Field(default="", alias="valueOut", max_length=1000)
    subtext: str = Field(default="", max_length=4000)
    visual_strategy: str = Field(
        default="",
        alias="visualStrategy",
        max_length=4000,
    )
    performance_notes: str = Field(
        default="",
        alias="performanceNotes",
        max_length=4000,
    )
    sound_notes: str = Field(
        default="",
        alias="soundNotes",
        max_length=3000,
    )

    model_config = {"populate_by_name": True}


class DramaEpisodePlanUpdate(BaseModel):
    time_scope: str = Field(
        default="",
        alias="timeScope",
        max_length=1000,
    )
    locations: list[str] = Field(default_factory=list, max_length=100)
    interior_exterior: list[str] = Field(
        default_factory=list,
        alias="interiorExterior",
        max_length=100,
    )
    characters: list[str] = Field(default_factory=list, max_length=100)
    scenes: list[str] = Field(default_factory=list, max_length=200)
    story_beats: list[str] = Field(
        default_factory=list,
        alias="storyBeats",
        max_length=200,
    )
    visual_requirements: list[str] = Field(
        default_factory=list,
        alias="visualRequirements",
        max_length=200,
    )
    dialogue_requirements: list[str] = Field(
        default_factory=list,
        alias="dialogueRequirements",
        max_length=200,
    )
    continuity_risks: list[str] = Field(
        default_factory=list,
        alias="continuityRisks",
        max_length=200,
    )
    scene_contracts: list[DramaSceneContractInput] = Field(
        default_factory=list,
        alias="sceneContracts",
        max_length=200,
    )

    model_config = {"populate_by_name": True}


class DramaSubtitleCueInput(BaseModel):
    start_seconds: float = Field(
        alias="startSeconds",
        ge=0,
        le=86400,
    )
    end_seconds: float = Field(
        alias="endSeconds",
        gt=0,
        le=86400,
    )
    text: str = Field(min_length=1, max_length=1000)

    model_config = {"populate_by_name": True}


class DramaSubtitlesUpdate(BaseModel):
    cues: list[DramaSubtitleCueInput] = Field(
        default_factory=list,
        max_length=1000,
    )


class DramaEpisodeRenderRequest(BaseModel):
    transition: str = Field(default="none", max_length=40)
    transition_duration: float = Field(
        default=0.4,
        alias="transitionDuration",
        ge=0.1,
        le=3,
    )
    strict_approvals: bool = Field(
        default=True,
        alias="strictApprovals",
    )

    model_config = {"populate_by_name": True}


class DramaProductionRunItemInput(BaseModel):
    target_type: str = Field(alias="targetType", max_length=40)
    target_id: str = Field(alias="targetId", min_length=1, max_length=80)
    slot: str = Field(min_length=1, max_length=80)
    title: str = Field(default="", max_length=200)
    request: dict[str, object] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class DramaProductionRunCreate(BaseModel):
    stage: str = Field(max_length=40)
    name: str = Field(default="", max_length=200)
    requires_approval: bool = Field(
        default=True,
        alias="requiresApproval",
    )
    max_parallel: int = Field(
        default=1,
        alias="maxParallel",
        ge=1,
        le=4,
    )
    items: list[DramaProductionRunItemInput] = Field(
        min_length=1,
        max_length=100,
    )

    model_config = {"populate_by_name": True}


class DramaProductionRunStart(BaseModel):
    approved_by: str = Field(
        default="local-user",
        alias="approvedBy",
        max_length=80,
    )

    model_config = {"populate_by_name": True}


class DramaSoundEffectInput(BaseModel):
    asset_id: str = Field(alias="assetId", max_length=80)
    start_seconds: float = Field(
        default=0,
        alias="startSeconds",
        ge=0,
        le=86400,
    )
    duration_seconds: float = Field(
        default=2,
        alias="durationSeconds",
        gt=0,
        le=3600,
    )
    volume_db: float = Field(
        default=-12,
        alias="volumeDb",
        ge=-60,
        le=12,
    )

    model_config = {"populate_by_name": True}


class DramaAudioMixUpdate(BaseModel):
    music_asset_id: str | None = Field(
        default=None,
        alias="musicAssetId",
        max_length=80,
    )
    music_volume_db: float = Field(
        default=-18,
        alias="musicVolumeDb",
        ge=-60,
        le=12,
    )
    ambience_asset_id: str | None = Field(
        default=None,
        alias="ambienceAssetId",
        max_length=80,
    )
    ambience_volume_db: float = Field(
        default=-22,
        alias="ambienceVolumeDb",
        ge=-60,
        le=12,
    )
    ducking: bool = True
    sound_effects: list[DramaSoundEffectInput] = Field(
        default_factory=list,
        alias="soundEffects",
        max_length=50,
    )

    model_config = {"populate_by_name": True}


class DramaSubtitleStyleUpdate(BaseModel):
    preset: str = Field(default="short_video", max_length=40)
    font_size: int = Field(
        default=30,
        alias="fontSize",
        ge=12,
        le=80,
    )
    outline: float = Field(default=2, ge=0, le=8)
    margin_v: int = Field(
        default=96,
        alias="marginV",
        ge=0,
        le=600,
    )
    primary_color: str = Field(
        default="#FFFFFF",
        alias="primaryColor",
        max_length=7,
    )
    outline_color: str = Field(
        default="#101010",
        alias="outlineColor",
        max_length=7,
    )

    model_config = {"populate_by_name": True}


class DramaSceneCreate(BaseModel):
    heading: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=4000)
    script_document_id: str | None = Field(
        default=None,
        alias="scriptDocumentId",
        max_length=80,
    )

    model_config = {"populate_by_name": True}


class DramaShotDirectionInput(BaseModel):
    shot_size: str = Field(default="", alias="shotSize", max_length=300)
    camera_angle: str = Field(
        default="",
        alias="cameraAngle",
        max_length=300,
    )
    camera_movement: str = Field(
        default="",
        alias="cameraMovement",
        max_length=500,
    )
    lens: str = Field(default="", max_length=300)
    blocking: str = Field(default="", max_length=2000)
    performance_action: str = Field(
        default="",
        alias="performanceAction",
        max_length=2000,
    )
    expression: str = Field(default="", max_length=1000)
    composition: str = Field(default="", max_length=2000)
    lighting: str = Field(default="", max_length=2000)
    sound: str = Field(default="", max_length=2000)
    transition: str = Field(default="", max_length=500)
    reference_notes: str = Field(
        default="",
        alias="referenceNotes",
        max_length=2000,
    )

    model_config = {"populate_by_name": True}


class DramaShotCreate(BaseModel):
    title: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=4000)
    dialogue: str = Field(default="", max_length=4000)
    duration_seconds: float = Field(
        default=5,
        alias="durationSeconds",
        ge=0.1,
        le=3600,
    )
    direction: DramaShotDirectionInput = Field(
        default_factory=DramaShotDirectionInput
    )

    model_config = {"populate_by_name": True}


class DramaShotUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    review_note: str = Field(
        default="",
        alias="reviewNote",
        max_length=2000,
    )
    first_frame_asset_id: str | None = Field(
        default=None,
        alias="firstFrameAssetId",
        max_length=80,
    )
    last_frame_asset_id: str | None = Field(
        default=None,
        alias="lastFrameAssetId",
        max_length=80,
    )
    grid9_asset_id: str | None = Field(
        default=None,
        alias="grid9AssetId",
        max_length=80,
    )
    storyboard_asset_id: str | None = Field(
        default=None,
        alias="storyboardAssetId",
        max_length=80,
    )
    video_asset_id: str | None = Field(
        default=None,
        alias="videoAssetId",
        max_length=80,
    )
    audio_asset_id: str | None = Field(
        default=None,
        alias="audioAssetId",
        max_length=80,
    )
    direction: DramaShotDirectionInput | None = Field(default=None)

    model_config = {"populate_by_name": True}


class DramaShotPromptUpdate(BaseModel):
    prompt: str = Field(default="", max_length=12000)


class DramaEntityCreate(BaseModel):
    kind: str = Field(max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    profile: dict[str, str] | None = Field(default=None, max_length=80)


class DramaEntityUpdate(BaseModel):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=4000)
    status: str = Field(default="draft", max_length=40)
    primary_asset_id: str | None = Field(
        default=None,
        alias="primaryAssetId",
        max_length=80,
    )
    reference_asset_ids: list[str] = Field(
        default_factory=list,
        alias="referenceAssetIds",
        max_length=100,
    )
    asset_slots: dict[str, str] = Field(
        default_factory=dict,
        alias="assetSlots",
        max_length=100,
    )
    profile: dict[str, str] | None = Field(default=None, max_length=80)
    voice_name: str | None = Field(
        default=None,
        alias="voiceName",
        max_length=160,
    )
    voice_rate: float = Field(
        default=0,
        alias="voiceRate",
        ge=-10,
        le=10,
    )

    model_config = {"populate_by_name": True}


class DramaEntityPromptUpdate(BaseModel):
    prompt: str = Field(default="", max_length=12000)


class DramaShotReferenceInput(BaseModel):
    entity_id: str = Field(alias="entityId", max_length=80)
    role: str = Field(default="reference", max_length=40)

    model_config = {"populate_by_name": True}


class DramaShotReferencesUpdate(BaseModel):
    references: list[DramaShotReferenceInput] = Field(
        default_factory=list,
        max_length=64,
    )


class DramaReviewCheckInput(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    passed: bool = False
    note: str = Field(default="", max_length=2000)


class DramaReviewCreate(BaseModel):
    stage: str = Field(max_length=40)
    role_id: str = Field(alias="roleId", max_length=80)
    status: str = Field(default="pending", max_length=40)
    score: float = Field(default=0, ge=0, le=100)
    checklist: list[DramaReviewCheckInput] = Field(
        default_factory=list,
        max_length=100,
    )
    feedback: str = Field(default="", max_length=10000)
    reviewer: str = Field(default="agent", max_length=40)

    model_config = {"populate_by_name": True}


class DramaStageDecision(BaseModel):
    feedback: str = Field(default="", max_length=10000)


class DramaAssetBinding(BaseModel):
    asset_id: str = Field(alias="assetId", min_length=1, max_length=80)

    model_config = {"populate_by_name": True}


class DramaAssetCandidateUpdate(BaseModel):
    status: str = Field(max_length=40)
