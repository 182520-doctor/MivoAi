import { getJson, requireJson } from "../../_shared/api/client";
import type {
  ImportedWorkflow,
  WorkflowCatalog,
  WorkflowInputs,
  WorkflowParameter,
} from "./types";

export function loadWorkflowCatalog() {
  return getJson<WorkflowCatalog>("/api/comfy/workflows");
}

export async function importWorkflow(
  filename: string,
  name: string,
  capability:
    | "image_generation"
    | "image_processing"
    | "video_generation"
    | "video_processing"
    | "audio_processing"
    | "transcription",
) {
  return requireJson<ImportedWorkflow>(
    await fetch("/api/comfy/workflows/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, name, capability }),
    }),
  );
}

export async function testWorkflow(
  workflowId: string,
  prompt: string,
  assetIds: string[] = [],
) {
  return requireJson<ImportedWorkflow>(
    await fetch(`/api/comfy/workflows/${workflowId}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, assetIds }),
    }),
  );
}

export async function setWorkflowEnabled(
  workflowId: string,
  enabled: boolean,
) {
  return requireJson<ImportedWorkflow>(
    await fetch(`/api/comfy/workflows/${workflowId}?enabled=${enabled}`, {
      method: "PATCH",
    }),
  );
}

export async function deleteWorkflow(workflowId: string) {
  return requireJson<{ workflowId: string; deleted: boolean }>(
    await fetch(`/api/comfy/workflows/${workflowId}`, {
      method: "DELETE",
    }),
  );
}

export async function updateWorkflowParameters(
  workflowId: string,
  parameters: WorkflowParameter[],
) {
  return requireJson<ImportedWorkflow>(
    await fetch(`/api/comfy/workflows/${workflowId}/parameters`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters }),
    }),
  );
}

export function loadWorkflowInputs(workflowId: string) {
  return getJson<WorkflowInputs>(
    `/api/comfy/workflows/${workflowId}/inputs`,
  );
}
