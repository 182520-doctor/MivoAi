import { getJson, putJson, requireJson } from "../../_shared/api/client";
import type { Model, ModelTestResult, Preferences } from "./types";

export async function loadModelCatalog() {
  const [models, preferences] = await Promise.all([
    getJson<Model[]>("/api/models"),
    getJson<Preferences>("/api/preferences"),
  ]);
  return { models, preferences };
}

export function saveTextModelPreference(modelId: string) {
  return saveModelPreferences({ defaultTextModelId: modelId });
}

export function saveModelPreferences(preferences: Partial<Preferences>) {
  return putJson<Preferences>("/api/preferences", preferences);
}

export function saveProviderKey(providerId: string, apiKey: string) {
  return putJson<{ configured: boolean }>(
    `/api/providers/${providerId}/credential`,
    { apiKey },
  );
}

export async function testTextModel(
  modelId: string,
  providerId: string,
  prompt: string,
) {
  return requireJson<ModelTestResult>(
    await fetch(`/api/models/${encodeURIComponent(modelId)}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ providerId, prompt }),
    }),
  );
}
