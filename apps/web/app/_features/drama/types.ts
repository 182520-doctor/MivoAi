export type DramaProject = {
  id: string;
  title: string;
  idea: string;
  format: string;
  visualStyle: string;
  status: string;
  activeStage: string;
  workspace: string | null;
  createdAt: string;
  updatedAt: string;
  stages: string[];
};

export type CreateDramaProjectInput = {
  idea: string;
  format: string;
  visualStyle: string;
  title?: string;
};

export type DramaDocumentKind = "brief" | "story_bible" | "script";

export type DramaDocument = {
  id: string;
  projectId: string;
  kind: DramaDocumentKind;
  version: number;
  status: "draft" | "approved";
  title: string;
  content: string;
  createdAt: string;
  updatedAt: string;
};

export type DramaEntityKind =
  | "character"
  | "costume"
  | "prop"
  | "location"
  | "style";

export type DramaEntity = {
  id: string;
  projectId: string;
  kind: DramaEntityKind;
  name: string;
  description: string;
  status: "draft" | "locked";
  primaryAssetId: string | null;
  referenceAssetIds: string[];
  assetSlots: Record<string, string>;
  assetPrompts: Record<string, string>;
  profile: Record<string, string>;
  voiceName: string | null;
  voiceRate: number;
  candidates?: DramaAssetCandidate[];
  createdAt: string;
  updatedAt: string;
};

export type DramaEntityReference = {
  entityId: string;
  role: string;
};

export type DramaAssetCandidate = {
  id: string;
  projectId: string;
  subjectType: "entity" | "shot";
  subjectId: string;
  slot: string;
  assetId: string;
  status: "candidate" | "selected" | "rejected" | "superseded";
  source: string;
  createdAt: string;
  updatedAt: string;
};

export type DramaShotStatusEvent = {
  id: string;
  shotId: string;
  fromStatus: DramaShot["status"];
  toStatus: DramaShot["status"];
  reviewer: "agent" | "user" | "system";
  note: string;
  createdAt: string;
};

export type DramaProductionRunItem = {
  id: string;
  position: number;
  targetType: "entity" | "shot";
  targetId: string;
  slot: string;
  title: string;
  status:
    | "pending"
    | "queued"
    | "running"
    | "succeeded"
    | "failed"
    | "skipped";
  generationTaskId: string | null;
  resultAssetId: string | null;
  error: string;
  request: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type DramaProductionRun = {
  id: string;
  projectId: string;
  episodeId: string;
  stage: string;
  name: string;
  status:
    | "draft"
    | "awaiting_approval"
    | "queued"
    | "running"
    | "partial"
    | "completed"
    | "failed"
    | "canceled";
  requiresApproval: boolean;
  maxParallel: number;
  approvedBy: string | null;
  startedAt: string | null;
  completedAt: string | null;
  planning: {
    source?: string;
    skipped?: Array<{ targetId: string; reason: string }>;
    model?: {
      providerId?: string;
      modelId?: string;
      name?: string;
      parameters?: Record<string, unknown>;
    };
  };
  createdAt: string;
  updatedAt: string;
  counts: Record<DramaProductionRunItem["status"], number>;
  items: DramaProductionRunItem[];
};

export type DramaShot = {
  id: string;
  sceneId: string;
  shotNumber: number;
  title: string;
  description: string;
  dialogue: string;
  durationSeconds: number;
  status: "planned" | "keyframe_ready" | "clip_ready" | "approved";
  firstFrameAssetId: string | null;
  lastFrameAssetId: string | null;
  grid9AssetId: string | null;
  storyboardAssetId: string | null;
  videoAssetId: string | null;
  audioAssetId: string | null;
  promptOverrides: Record<string, string>;
  direction: DramaShotDirection;
  entityReferences?: DramaEntityReference[];
  candidates?: DramaAssetCandidate[];
  statusHistory?: DramaShotStatusEvent[];
  createdAt: string;
  updatedAt: string;
};

export type DramaShotDirection = {
  shotSize: string;
  cameraAngle: string;
  cameraMovement: string;
  lens: string;
  blocking: string;
  performanceAction: string;
  expression: string;
  composition: string;
  lighting: string;
  sound: string;
  transition: string;
  referenceNotes: string;
};

export type DramaSubtitleCue = {
  startSeconds: number;
  endSeconds: number;
  text: string;
};

export type DramaAudioMix = {
  soundEffects: DramaSoundEffect[];
  musicAssetId: string | null;
  musicVolumeDb: number;
  ambienceAssetId: string | null;
  ambienceVolumeDb: number;
  ducking: boolean;
};

export type DramaSoundEffect = {
  assetId: string;
  startSeconds: number;
  durationSeconds: number;
  volumeDb: number;
};

export type DramaAuditIssue = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  shotId: string | null;
  entityId: string | null;
};

export type DramaAudit = {
  projectId: string;
  score: number;
  ready: boolean;
  entityCount: number;
  shotCount: number;
  errorCount: number;
  warningCount: number;
  issues: DramaAuditIssue[];
};

export type DramaEpisodeAudit = {
  episodeId: string;
  episodeNumber: number;
  title: string;
  score: number;
  readyForAssets: boolean;
  readyForVideo: boolean;
  sceneCount: number;
  shotCount: number;
  dialogueShotCount: number;
  unboundShotCount: number;
  scenePlanMismatchCount: number;
  dialogueSpeakerIssueCount: number;
  errorCount: number;
  warningCount: number;
  issues: DramaAuditIssue[];
};

export type DramaSubtitleStyle = {
  preset: "short_video" | "cinema" | "minimal" | "custom";
  fontSize: number;
  outline: number;
  marginV: number;
  primaryColor: string;
  outlineColor: string;
};

export type DramaScene = {
  id: string;
  episodeId: string;
  sceneNumber: number;
  heading: string;
  summary: string;
  scriptDocumentId: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  shots: DramaShot[];
};

export type DramaEpisodePlan = {
  timeScope: string;
  locations: string[];
  interiorExterior: string[];
  characters: string[];
  scenes: string[];
  storyBeats: string[];
  visualRequirements: string[];
  dialogueRequirements: string[];
  continuityRisks: string[];
  sceneContracts: DramaSceneContract[];
};

export type DramaSceneContract = {
  sceneNumber: number;
  title: string;
  valueIn: string;
  characterObjectives: string[];
  obstacle: string;
  tactics: string[];
  beats: string[];
  turn: string;
  valueOut: string;
  subtext: string;
  visualStrategy: string;
  performanceNotes: string;
  soundNotes: string;
};

export type DramaEpisode = {
  id: string;
  projectId: string;
  episodeNumber: number;
  title: string;
  synopsis: string;
  status: string;
  exportAssetId: string | null;
  exportManifestId: string | null;
  subtitleCues: DramaSubtitleCue[];
  subtitleStyle: DramaSubtitleStyle;
  audioMix: DramaAudioMix;
  plan: DramaEpisodePlan;
  createdAt: string;
  updatedAt: string;
  scenes: DramaScene[];
};

export type DramaSeriesEpisode = {
  id: string;
  episodeNumber: number;
  title: string;
  synopsis: string;
  status: string | null;
  planComplete: boolean;
  sceneCount: number;
  shotCount: number;
  keyframesReady: number;
  videosReady: number;
  shotsApproved: number;
  rendered: boolean;
  nextAction: string;
  nextActionLabel: string;
  queueState:
    | "awaiting_approval"
    | "running"
    | "needs_retry"
    | "blocked"
    | "ready"
    | "completed";
  queueLabel: string;
  missingKeyframes: Array<{ id: string; title: string }>;
  missingVideos: Array<{ id: string; title: string }>;
  unreviewedShots: Array<{ id: string; title: string }>;
  assetCoverage: {
    referenced: number;
    ready: number;
    locked: number;
  };
  gates: Record<
    string,
    { status: string; label: string; approved: boolean }
  >;
  latestRun: {
    id: string;
    name: string;
    stage: string;
    status: string;
    updatedAt: string;
  } | null;
};

export type DramaSeriesOverview = {
  projectId: string;
  projectTitle: string;
  totals: {
    episodes: number;
    plansComplete: number;
    scenes: number;
    shots: number;
    keyframesReady: number;
    videosReady: number;
    shotsApproved: number;
    episodesRendered: number;
    episodesAwaitingApproval: number;
    episodesRunning: number;
    episodesNeedingRetry: number;
    episodesReadyToAdvance: number;
  };
  episodes: DramaSeriesEpisode[];
};

export type DramaProductionRole = {
  id: string;
  title: string;
  department: string;
  description: string;
  stageIds: string[];
  responsibilities: string[];
  requiredInputs: string[];
  deliverables: string[];
  checklist: string[];
  reviewCriteria: string[];
};

export type DramaReviewCheck = {
  key: string;
  label: string;
  passed: boolean;
  note: string;
};

export type DramaReview = {
  id: string;
  projectId: string;
  stage: string;
  roleId: string;
  status: "pending" | "passed" | "changes_requested" | "failed";
  score: number;
  checklist: DramaReviewCheck[];
  feedback: string;
  reviewer: "agent" | "user" | "system";
  artifactRevision: number;
  createdAt: string;
  updatedAt: string;
};

export type DramaStageGate = {
  stage: string;
  ownerRoleIds: string[];
  owners: Array<{
    id: string;
    title: string;
    department: string;
  }>;
  status:
    | "pending"
    | "in_review"
    | "awaiting_user"
    | "changes_requested"
    | "failed"
    | "approved";
  label: string;
  revision: number;
  approvedRevision: number | null;
  stale: boolean;
  lastChangeReason: string;
  score: number | null;
  approved: boolean;
  agentReady: boolean;
  latestReviews: Record<string, DramaReview>;
  userDecision: DramaReview | null;
};

export type DramaControlRoom = {
  project: DramaProject;
  roles: DramaProductionRole[];
  currentStage: DramaStageGate;
  gates: DramaStageGate[];
  episodes: Array<{
    id: string;
    episodeNumber: number;
    title: string;
    synopsis: string;
    plan: DramaEpisodePlan;
    planComplete: boolean;
  }>;
};
