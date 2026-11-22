import { getJson, requireJson } from "../../_shared/api/client";
import type {
  CreateDramaProjectInput,
  DramaAssetCandidate,
  DramaDocument,
  DramaDocumentKind,
  DramaEpisodeAudit,
  DramaAudioMix,
  DramaAudit,
  DramaControlRoom,
  DramaEntity,
  DramaEntityKind,
  DramaEntityReference,
  DramaEpisode,
  DramaEpisodePlan,
  DramaProject,
  DramaProductionRun,
  DramaProductionRole,
  DramaReview,
  DramaSeriesOverview,
  DramaScene,
  DramaShot,
  DramaShotDirection,
  DramaStageGate,
  DramaSubtitleStyle,
  DramaSubtitleCue,
} from "./types";

export function loadDramaProjects(limit = 100) {
  return getJson<DramaProject[]>(`/api/drama/projects?limit=${limit}`);
}

export async function createDramaProject(input: CreateDramaProjectInput) {
  return requireJson<DramaProject>(
    await fetch("/api/drama/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateDramaProjectStage(
  projectId: string,
  activeStage: string,
  status?: string,
) {
  return requireJson<DramaProject>(
    await fetch(`/api/drama/projects/${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activeStage, status }),
    }),
  );
}

export function loadDramaDocuments(projectId: string) {
  return getJson<DramaDocument[]>(
    `/api/drama/projects/${projectId}/documents`,
  );
}

export async function createDramaDocument(
  projectId: string,
  input: {
    kind: DramaDocumentKind;
    title: string;
    content: string;
  },
) {
  return requireJson<DramaDocument>(
    await fetch(`/api/drama/projects/${projectId}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateDramaDocument(
  documentId: string,
  title: string,
  content: string,
) {
  return requireJson<DramaDocument>(
    await fetch(`/api/drama/projects/documents/${documentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content }),
    }),
  );
}

export async function approveDramaDocument(documentId: string) {
  return requireJson<DramaDocument>(
    await fetch(
      `/api/drama/projects/documents/${documentId}/approve`,
      { method: "POST" },
    ),
  );
}

export function loadDramaProduction(projectId: string) {
  return getJson<DramaEpisode[]>(
    `/api/drama/projects/${projectId}/production`,
  );
}

export function loadDramaSeries(projectId: string) {
  return getJson<DramaSeriesOverview>(
    `/api/drama/projects/${projectId}/series-production`,
  );
}

export function loadDramaAudit(projectId: string) {
  return getJson<DramaAudit>(`/api/drama/projects/${projectId}/audit`);
}

export function loadDramaEpisodeAudit(episodeId: string) {
  return getJson<DramaEpisodeAudit>(
    `/api/drama/projects/episodes/${episodeId}/audit`,
  );
}

export function loadDramaRoles(stage?: string) {
  const query = stage ? `?stage=${encodeURIComponent(stage)}` : "";
  return getJson<DramaProductionRole[]>(`/api/drama/projects/roles${query}`);
}

export function loadDramaControlRoom(projectId: string) {
  return getJson<DramaControlRoom>(
    `/api/drama/projects/${projectId}/production-control`,
  );
}

export function loadDramaReviews(projectId: string, stage?: string) {
  const query = stage ? `?stage=${encodeURIComponent(stage)}` : "";
  return getJson<DramaReview[]>(
    `/api/drama/projects/${projectId}/reviews${query}`,
  );
}

export async function decideDramaStage(
  projectId: string,
  stage: string,
  approved: boolean,
  feedback = "",
) {
  return requireJson<DramaStageGate>(
    await fetch(
      `/api/drama/projects/${projectId}/stages/${stage}/${
        approved ? "approve" : "request-changes"
      }`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback }),
      },
    ),
  );
}

export async function createDramaEpisode(
  projectId: string,
  title: string,
  synopsis = "",
) {
  return requireJson<DramaEpisode>(
    await fetch(`/api/drama/projects/${projectId}/episodes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, synopsis }),
    }),
  );
}

export async function saveDramaEpisodePlan(
  episodeId: string,
  plan: DramaEpisodePlan,
) {
  return requireJson<DramaEpisode>(
    await fetch(`/api/drama/projects/episodes/${episodeId}/plan`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(plan),
    }),
  );
}

export async function createDramaScene(
  episodeId: string,
  heading: string,
  summary = "",
  scriptDocumentId: string | null = null,
) {
  return requireJson<DramaScene>(
    await fetch(
      `/api/drama/projects/episodes/${episodeId}/scenes`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          heading,
          summary,
          scriptDocumentId,
        }),
      },
    ),
  );
}

export async function createDramaShot(
  sceneId: string,
  input: {
    title: string;
    description?: string;
    dialogue?: string;
    durationSeconds?: number;
  },
) {
  return requireJson<DramaShot>(
    await fetch(`/api/drama/projects/scenes/${sceneId}/shots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function renderDramaEpisode(
  episodeId: string,
  transition = "none",
  transitionDuration = 0.4,
) {
  return requireJson<DramaEpisode>(
    await fetch(
      `/api/drama/projects/episodes/${episodeId}/render`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transition, transitionDuration }),
      },
    ),
  );
}

export async function saveDramaSubtitles(
  episodeId: string,
  cues: DramaSubtitleCue[],
) {
  return requireJson<{ cues: DramaSubtitleCue[] }>(
    await fetch(
      `/api/drama/projects/episodes/${episodeId}/subtitles`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cues }),
      },
    ),
  );
}

export async function saveDramaAudioMix(
  episodeId: string,
  input: DramaAudioMix,
) {
  return requireJson<DramaAudioMix>(
    await fetch(
      `/api/drama/projects/episodes/${episodeId}/audio-mix`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
    ),
  );
}

export async function saveDramaSubtitleStyle(
  episodeId: string,
  input: DramaSubtitleStyle,
) {
  return requireJson<DramaSubtitleStyle>(
    await fetch(
      `/api/drama/projects/episodes/${episodeId}/subtitle-style`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
    ),
  );
}

export function loadDramaProductionRuns(
  projectId: string,
  episodeId?: string | null,
  limit = 20,
) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (episodeId) query.set("episodeId", episodeId);
  return getJson<DramaProductionRun[]>(
    `/api/drama/projects/${projectId}/production-runs?${query}`,
  );
}

export function loadDramaProductionRun(runId: string) {
  return getJson<DramaProductionRun>(
    `/api/drama/projects/production-runs/${runId}`,
  );
}

export async function startDramaProductionRun(
  runId: string,
  approvedBy = "local-user",
) {
  return requireJson<DramaProductionRun>(
    await fetch(
      `/api/drama/projects/production-runs/${runId}/start`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approvedBy }),
      },
    ),
  );
}

export async function retryDramaProductionRun(
  runId: string,
  approvedBy = "local-user",
) {
  return requireJson<DramaProductionRun>(
    await fetch(
      `/api/drama/projects/production-runs/${runId}/retry-failed`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approvedBy }),
      },
    ),
  );
}

export async function cancelDramaProductionRun(runId: string) {
  return requireJson<DramaProductionRun>(
    await fetch(
      `/api/drama/projects/production-runs/${runId}/cancel`,
      { method: "POST" },
    ),
  );
}

export async function updateDramaShotStatus(
  shotId: string,
  status: DramaShot["status"],
  reviewNote = "",
) {
  return updateDramaShot(shotId, {
    status,
    reviewNote,
  });
}

export async function updateDramaShot(
  shotId: string,
  input: Partial<
    Pick<
      DramaShot,
      | "status"
      | "firstFrameAssetId"
      | "lastFrameAssetId"
      | "grid9AssetId"
      | "storyboardAssetId"
      | "videoAssetId"
      | "audioAssetId"
    >
  > & { reviewNote?: string },
) {
  return requireJson<DramaShot>(
    await fetch(`/api/drama/projects/shots/${shotId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function saveDramaShotPrompt(
  shotId: string,
  slot: string,
  prompt: string,
) {
  return requireJson<DramaShot>(
    await fetch(
      `/api/drama/projects/shots/${shotId}/prompts/${encodeURIComponent(slot)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      },
    ),
  );
}

export async function updateDramaShotDirection(
  shotId: string,
  direction: DramaShotDirection,
) {
  return requireJson<DramaShot>(
    await fetch(`/api/drama/projects/shots/${shotId}/direction`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(direction),
    }),
  );
}

export function loadDramaEntities(projectId: string) {
  return getJson<DramaEntity[]>(
    `/api/drama/projects/${projectId}/entities`,
  );
}

export async function createDramaEntity(
  projectId: string,
  input: {
    kind: DramaEntityKind;
    name: string;
    description?: string;
  },
) {
  return requireJson<DramaEntity>(
    await fetch(`/api/drama/projects/${projectId}/entities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateDramaEntity(
  entityId: string,
  input: {
    name: string;
    description: string;
    status: DramaEntity["status"];
    primaryAssetId: string | null;
    referenceAssetIds: string[];
    assetSlots?: Record<string, string>;
    profile?: Record<string, string>;
    voiceName?: string | null;
    voiceRate?: number;
  },
) {
  return requireJson<DramaEntity>(
    await fetch(`/api/drama/projects/entities/${entityId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function bindDramaEntityAsset(
  entityId: string,
  slot: string,
  assetId: string,
) {
  return requireJson<DramaEntity>(
    await fetch(
      `/api/drama/projects/entities/${entityId}/asset-slots/${encodeURIComponent(slot)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assetId }),
      },
    ),
  );
}

export async function saveDramaEntityPrompt(
  entityId: string,
  slot: string,
  prompt: string,
) {
  return requireJson<DramaEntity>(
    await fetch(
      `/api/drama/projects/entities/${entityId}/prompts/${encodeURIComponent(slot)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      },
    ),
  );
}

export async function bindDramaShotAsset(
  shotId: string,
  slot: string,
  assetId: string,
) {
  return requireJson<DramaShot>(
    await fetch(
      `/api/drama/projects/shots/${shotId}/asset-slots/${encodeURIComponent(slot)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assetId }),
      },
    ),
  );
}

export async function updateDramaAssetCandidate(
  candidateId: string,
  status: "candidate" | "selected" | "rejected",
) {
  return requireJson<DramaAssetCandidate>(
    await fetch(
      `/api/drama/projects/asset-candidates/${candidateId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    ),
  );
}

export async function loadDramaShotReferences(shotId: string) {
  return requireJson<{ references: DramaEntityReference[] }>(
    await fetch(`/api/drama/projects/shots/${shotId}/references`),
  );
}

export async function updateDramaShotReferences(
  shotId: string,
  references: DramaEntityReference[],
) {
  return requireJson<{ references: DramaEntityReference[] }>(
    await fetch(`/api/drama/projects/shots/${shotId}/references`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ references }),
    }),
  );
}
