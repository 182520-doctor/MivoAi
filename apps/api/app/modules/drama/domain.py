"""Short-drama project aggregate, production roles and review gates."""

from __future__ import annotations

from dataclasses import dataclass

DRAMA_STAGES = (
    "brief",
    "bible",
    "script",
    "breakdown",
    "assets",
    "keyframes",
    "clips",
    "timeline",
)

DRAMA_DOCUMENT_KINDS = ("brief", "story_bible", "script")
DRAMA_ENTITY_KINDS = ("character", "costume", "prop", "location", "style")
DRAMA_REVIEW_STATUSES = (
    "pending",
    "passed",
    "changes_requested",
    "failed",
)
DRAMA_CANDIDATE_SUBJECT_TYPES = ("entity", "shot")
DRAMA_CANDIDATE_STATUSES = (
    "candidate",
    "selected",
    "rejected",
    "superseded",
)
DRAMA_RUN_STATUSES = (
    "draft",
    "awaiting_approval",
    "queued",
    "running",
    "partial",
    "completed",
    "failed",
    "canceled",
)
DRAMA_RUN_ITEM_STATUSES = (
    "pending",
    "queued",
    "running",
    "succeeded",
    "failed",
    "skipped",
)


@dataclass(frozen=True, slots=True)
class DramaProductionRole:
    """A professional responsibility contract used by the Agent and UI."""

    id: str
    title: str
    department: str
    description: str
    stage_ids: tuple[str, ...]
    responsibilities: tuple[str, ...]
    required_inputs: tuple[str, ...]
    deliverables: tuple[str, ...]
    checklist: tuple[str, ...]
    review_criteria: tuple[str, ...]


DRAMA_PRODUCTION_ROLES = (
    DramaProductionRole(
        id="screenwriter",
        title="编剧",
        department="创作",
        description="把创意转化为可拍摄、可拆解、可持续修订的结构化剧本。",
        stage_ids=("brief", "bible", "script"),
        responsibilities=(
            "确认题材、受众、单集时长、叙事视角和内容边界",
            "建立人物的外在目标、内在需求、创伤、错误信念、恐惧、矛盾与成长弧线",
            "为每场戏定义进入价值、人物目标、障碍、战术、转折和退出价值",
            "把故事拆成可分集推进的冲突、递进与钩子，避免靠巧合或强行反转续命",
        ),
        required_inputs=(
            "用户确认的故事方向与视觉风格",
            "目标平台、单集时长和集数",
            "禁用元素、审核尺度和结局倾向",
        ),
        deliverables=(
            "项目 Brief",
            "故事圣经",
            "分集大纲与正式剧本版本",
        ),
        checklist=(
            "每集都有清晰目标、逐级升级的障碍、价值转折和有机钩子",
            "对白短、可表演、有潜台词，角色声音可区分，不解释观众已经看见的信息",
            "动作行写可见行为与反应，不越权堆砌镜头术语，也不写成小说心理独白",
            "场次标题包含内外景、地点和时间，场景元素足以支持拆解和制片",
        ),
        review_criteria=(
            "故事方向已由用户明确确认",
            "剧本结构与故事圣经无冲突",
            "每个场景都改变人物处境、关系、信息或情绪，删除后会造成实质损失",
            "所有关键剧情都能落到可拍摄的动作、对白、声音或视觉信息",
        ),
    ),
    DramaProductionRole(
        id="director",
        title="导演",
        department="导演组",
        description="守住全剧叙事、表演、视觉和节奏的统一表达。",
        stage_ids=("bible", "script", "breakdown", "keyframes", "clips", "timeline"),
        responsibilities=(
            "把台词翻译为演员可执行的目标、障碍、战术、反应，以及声、台、形、表要求",
            "确定叙事节奏、场面调度、镜头语言、表演基调和情绪曲线",
            "审核关键帧、镜头运动和成片是否准确表达场面价值变化",
            "在成本、质量与连续性之间做最终创作取舍",
        ),
        required_inputs=(
            "已确认的故事圣经和剧本",
            "视觉风格、角色资产和关键场景",
            "单集节奏与重点情绪节点",
        ),
        deliverables=(
            "导演阐述",
            "镜头语言规则",
            "关键帧与镜头审核结论",
        ),
        checklist=(
            "每个镜头都有景别、角度、机位、运动、主体调度和叙事目的",
            "覆盖镜头能完成剪辑，保持 180° 轴线、视线、屏幕方向和动作接力",
            "表演以动作和反应承载情绪，不依赖夸张表情或解释性台词",
            "声音、停顿、呼吸、走位、手势与道具使用服务人物目标和潜台词",
        ),
        review_criteria=(
            "镜头方案能准确表达剧本动作与对白",
            "关键镜头不依赖观众猜测未展示的信息",
            "不为了炫技牺牲可读性、连续性和制作稳定性",
        ),
    ),
    DramaProductionRole(
        id="production_designer",
        title="场景师 / 美术指导",
        department="美术组",
        description="建立人物所处世界的空间、材质、色彩和时代规则。",
        stage_ids=("bible", "assets", "keyframes"),
        responsibilities=(
            "设计总场景、分场景、内外景和转场空间",
            "确定陈设、材质、色彩、年代和环境影响",
            "为镜头复用准备统一场景主图与变体",
        ),
        required_inputs=(
            "故事圣经中的时代、地域和社会阶层",
            "场次表、人物行动和剧情时间",
            "视觉风格与色彩规则",
        ),
        deliverables=(
            "场景总图",
            "分场景与内外景概念图",
            "关键空间和美术连续性说明",
        ),
        checklist=(
            "场景符合时代、地域、身份和剧情功能",
            "场景主图与分场景共享固定空间逻辑",
            "门窗、家具、陈设和光源位置可持续复用",
        ),
        review_criteria=(
            "每个主要场次都有可引用的场景资产",
            "不同场次之间没有无解释的空间漂移",
            "场景信息支持人物行动和镜头调度",
        ),
    ),
    DramaProductionRole(
        id="costume_makeup",
        title="定妆 / 服装师",
        department="造型组",
        description="保证角色身份、服装、发型、妆造和道具在镜头间连续。",
        stage_ids=("bible", "assets", "keyframes"),
        responsibilities=(
            "用一张 16:9 角色设定总表同时建立头部特写、全身正/侧/背视图、表情特写和服饰细节",
            "定义服装层次、材质、纹样、发饰和妆容",
            "标记剧情中的换装、受伤、污损和道具携带状态",
        ),
        required_inputs=(
            "角色身份、年龄、性格和时代背景",
            "角色关系和每集造型变化",
            "镜头动作与光线条件",
        ),
        deliverables=(
            "单张 16:9 角色设定总表",
            "换装和连续性记录",
        ),
        checklist=(
            "角色总表内的头部、三面全身、表情和服饰来自同一身份且比例一致",
            "服装纹样、配饰和左右方向不漂移",
            "每场戏的造型状态与剧情时间一致",
        ),
        review_criteria=(
            "主要角色已绑定单张 16:9 角色设定总表和主视觉",
            "镜头引用能够唯一识别角色身份",
            "造型变化有剧情依据并已记录",
        ),
    ),
    DramaProductionRole(
        id="lighting",
        title="灯光师",
        department="摄影灯光组",
        description="用光源方向、色温、反差和氛围维持空间真实与情绪连续。",
        stage_ids=("assets", "keyframes", "clips"),
        responsibilities=(
            "确定日景、夜景、室内外光源和色温规则",
            "为角色和场景建立灯光参考",
            "检查跨镜头光源、曝光和影子方向",
        ),
        required_inputs=(
            "场次时间、内外景和空间结构",
            "视觉风格和情绪基调",
            "关键帧与角色资产",
        ),
        deliverables=(
            "灯光参考图",
            "每场光线说明",
            "关键帧曝光与色温修正建议",
        ),
        checklist=(
            "主光方向与窗户、灯具和场景结构一致",
            "相邻镜头色温和曝光没有跳变",
            "夜景可读，不牺牲人物脸部和动作",
        ),
        review_criteria=(
            "关键帧光源方向有明确依据",
            "同一空间同一时间的光线风格连续",
            "灯光服务叙事且不影响后续视频一致性",
        ),
    ),
    DramaProductionRole(
        id="continuity_supervisor",
        title="场记 / 连续性监督",
        department="制片组",
        description="在拆解与制作前发现人物、时间、空间、道具和对白矛盾。",
        stage_ids=("breakdown", "assets", "keyframes", "clips", "timeline"),
        responsibilities=(
            "逐集检查时间、地点、人物、场景、动作和对白",
            "维护道具、服装、伤势、天气和时间连续性",
            "把风险转化为可执行的镜头和资产检查项",
        ),
        required_inputs=(
            "已确认剧本和分集计划",
            "场次、镜头、资产引用和台词",
            "关键帧、视频和字幕状态",
        ),
        deliverables=(
            "连续性检查表",
            "冲突清单和修正建议",
            "制作风险与待确认事项",
        ),
        checklist=(
            "时间推进和地点转换清楚",
            "人物位置、动作接力、服装和道具连续",
            "画面描述与对白不互相矛盾",
        ),
        review_criteria=(
            "阻断后续制作的问题已修复",
            "剩余风险已明确标记并由用户知悉",
            "每个镜头都能追溯到剧本动作和资产",
        ),
    ),
    DramaProductionRole(
        id="first_assistant_director",
        title="执行导演",
        department="导演组",
        description="把创意方案转成可执行的分集、场次、镜头和制作清单。",
        stage_ids=("breakdown", "assets", "keyframes", "clips", "timeline"),
        responsibilities=(
            "按集拆解时间、地点、人物、场景、故事节拍和镜头",
            "定义首帧、尾帧、九宫格、故事板和视频生成需求",
            "编排制作顺序、依赖、审核门和返工范围",
        ),
        required_inputs=(
            "已审批剧本和导演阐述",
            "角色、场景、服装、道具和风格资产",
            "模型能力与镜头工作流参数",
        ),
        deliverables=(
            "分集制作计划",
            "场次镜头表和资产需求表",
            "关键帧、故事板和视频任务清单",
        ),
        checklist=(
            "每集计划覆盖时间、地点、人物、场景和故事",
            "镜头有明确画面、对白、时长和参考资产",
            "首帧、尾帧、九宫格与故事板需求匹配镜头复杂度",
        ),
        review_criteria=(
            "模板化字段无空白或占位符",
            "每个镜头都能选择兼容的生成工作流",
            "资产缺失、参数缺失和冲突在生成前被发现",
        ),
    ),
    DramaProductionRole(
        id="editor",
        title="剪辑 / 声音",
        department="后期组",
        description="通过镜头顺序、节奏、声音、字幕和转场完成整集成片。",
        stage_ids=("clips", "timeline"),
        responsibilities=(
            "组织镜头顺序、节奏、转场和情绪落点",
            "整合对白、环境声、音乐、音效和字幕",
            "输出可追溯、可重建的整集时间线",
        ),
        required_inputs=(
            "已审核镜头视频和关键帧",
            "对白、配音、字幕和声音素材",
            "剪辑节奏、画幅和输出规范",
        ),
        deliverables=(
            "镜头声音与字幕状态",
            "整集时间线",
            "最终导出与制作清单",
        ),
        checklist=(
            "镜头顺序、时长和转场符合叙事节奏",
            "对白、字幕、音效和音乐层级清楚",
            "成片规格、画幅和帧率符合项目要求",
        ),
        review_criteria=(
            "所有镜头视频可播放且已绑定",
            "字幕与对白一致，声音响度可控",
            "最终成片可由固定版本素材重建",
        ),
    ),
)

DRAMA_STAGE_OWNERS = {
    "brief": ("screenwriter",),
    "bible": ("screenwriter", "director", "production_designer", "costume_makeup"),
    "script": ("screenwriter", "director"),
    "breakdown": ("director", "continuity_supervisor", "first_assistant_director"),
    "assets": ("production_designer", "costume_makeup", "lighting"),
    "keyframes": ("director", "lighting", "first_assistant_director"),
    "clips": ("director", "continuity_supervisor", "first_assistant_director"),
    "timeline": ("director", "continuity_supervisor", "editor"),
}


@dataclass(frozen=True, slots=True)
class DramaProject:
    """Top-level aggregate for one short-drama production."""

    id: str
    title: str
    idea: str
    format: str
    visual_style: str
    status: str
    active_stage: str
    workspace_path: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaDocument:
    """A versioned production document owned by one drama project."""

    id: str
    project_id: str
    kind: str
    version: int
    status: str
    title: str
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaSubtitleCue:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class DramaAudioMix:
    sound_effects: tuple[DramaSoundEffect, ...] = ()
    music_asset_id: str | None = None
    music_volume_db: float = -18.0
    ambience_asset_id: str | None = None
    ambience_volume_db: float = -22.0
    ducking: bool = True


@dataclass(frozen=True, slots=True)
class DramaSoundEffect:
    asset_id: str
    start_seconds: float
    duration_seconds: float
    volume_db: float


@dataclass(frozen=True, slots=True)
class DramaSubtitleStyle:
    preset: str = "short_video"
    font_size: int = 30
    outline: float = 2
    margin_v: int = 96
    primary_color: str = "#FFFFFF"
    outline_color: str = "#101010"


@dataclass(frozen=True, slots=True)
class DramaSceneContract:
    scene_number: int
    title: str = ""
    value_in: str = ""
    character_objectives: tuple[str, ...] = ()
    obstacle: str = ""
    tactics: tuple[str, ...] = ()
    beats: tuple[str, ...] = ()
    turn: str = ""
    value_out: str = ""
    subtext: str = ""
    visual_strategy: str = ""
    performance_notes: str = ""
    sound_notes: str = ""


@dataclass(frozen=True, slots=True)
class DramaEpisodePlan:
    time_scope: str = ""
    locations: tuple[str, ...] = ()
    interior_exterior: tuple[str, ...] = ()
    characters: tuple[str, ...] = ()
    scenes: tuple[str, ...] = ()
    story_beats: tuple[str, ...] = ()
    visual_requirements: tuple[str, ...] = ()
    dialogue_requirements: tuple[str, ...] = ()
    continuity_risks: tuple[str, ...] = ()
    scene_contracts: tuple[DramaSceneContract, ...] = ()


@dataclass(frozen=True, slots=True)
class DramaEpisode:
    id: str
    project_id: str
    episode_number: int
    title: str
    synopsis: str
    status: str
    export_asset_id: str | None
    export_manifest_id: str | None
    subtitle_cues: tuple[DramaSubtitleCue, ...]
    subtitle_style: DramaSubtitleStyle
    audio_mix: DramaAudioMix
    plan: DramaEpisodePlan
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaExportManifest:
    id: str
    project_id: str
    episode_id: str
    export_asset_id: str
    manifest: dict[str, object]
    created_at: str


@dataclass(frozen=True, slots=True)
class DramaScene:
    id: str
    episode_id: str
    scene_number: int
    heading: str
    summary: str
    script_document_id: str | None
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaShot:
    id: str
    scene_id: str
    shot_number: int
    title: str
    description: str
    dialogue: str
    duration_seconds: float
    status: str
    first_frame_asset_id: str | None
    last_frame_asset_id: str | None
    grid9_asset_id: str | None
    storyboard_asset_id: str | None
    video_asset_id: str | None
    audio_asset_id: str | None
    prompt_overrides: dict[str, str]
    direction: dict[str, str]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaEntity:
    id: str
    project_id: str
    kind: str
    name: str
    description: str
    status: str
    primary_asset_id: str | None
    reference_asset_ids: tuple[str, ...]
    asset_slots: dict[str, str]
    asset_prompts: dict[str, str]
    profile: dict[str, str]
    voice_name: str | None
    voice_rate: float
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaShotEntityReference:
    shot_id: str
    entity_id: str
    role: str


@dataclass(frozen=True, slots=True)
class DramaShotStatusEvent:
    id: str
    shot_id: str
    from_status: str
    to_status: str
    reviewer: str
    note: str
    created_at: str


@dataclass(frozen=True, slots=True)
class DramaAssetCandidate:
    """One durable candidate for an entity or shot asset slot."""

    id: str
    project_id: str
    subject_type: str
    subject_id: str
    slot: str
    asset_id: str
    status: str
    source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaProductionRunItem:
    id: str
    run_id: str
    position: int
    target_type: str
    target_id: str
    slot: str
    title: str
    status: str
    generation_task_id: str | None
    result_asset_id: str | None
    error: str
    request: dict[str, object]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaProductionRun:
    id: str
    project_id: str
    episode_id: str
    stage: str
    name: str
    status: str
    requires_approval: bool
    max_parallel: int
    approved_by: str | None
    started_at: str | None
    completed_at: str | None
    planning: dict[str, object]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaStageRevision:
    project_id: str
    stage: str
    revision: int
    approved_revision: int | None
    approved_by: str | None
    approved_at: str | None
    last_change_reason: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DramaReviewCheck:
    key: str
    label: str
    passed: bool
    note: str = ""


@dataclass(frozen=True, slots=True)
class DramaReview:
    id: str
    project_id: str
    stage: str
    role_id: str
    status: str
    score: float
    checklist: tuple[DramaReviewCheck, ...]
    feedback: str
    reviewer: str
    artifact_revision: int
    created_at: str
    updated_at: str
