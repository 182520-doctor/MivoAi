import { getJson, requireJson } from "../../_shared/api/client";
import type { MediaGenerationInput, MediaTask } from "./types";

export async function createMediaTask(input: MediaGenerationInput) {
  return requireJson<MediaTask>(
    await fetch("/api/generations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function uploadMediaAssets(files: File[]) {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return requireJson<{ assetIds: string[] }>(
    await fetch("/api/assets/upload", {
      method: "POST",
      body,
    }),
  );
}

export function getMediaTask(taskId: string) {
  return getJson<MediaTask>(`/api/generations/${taskId}`);
}

export async function pollMediaTask(
  taskId: string,
  onUpdate: (task: MediaTask) => void,
  signal: AbortSignal,
) {
  while (!signal.aborted) {
    const task = await getMediaTask(taskId);
    onUpdate(task);
    if (["succeeded", "failed", "canceled"].includes(task.status)) {
      return task;
    }
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(resolve, 1500);
      signal.addEventListener(
        "abort",
        () => {
          window.clearTimeout(timer);
          reject(new DOMException("Aborted", "AbortError"));
        },
        { once: true },
      );
    });
  }
  throw new DOMException("Aborted", "AbortError");
}

export function mediaAssetUrl(assetId: string) {
  return `/api/assets/${assetId}`;
}
