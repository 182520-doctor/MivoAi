import { requestJson } from "../../../shared/api/http";
import type { Model, Preferences } from "../types";

export const modelsApi = {
  list: (signal?: AbortSignal) =>
    requestJson<Model[]>("/api/models", { signal }),
  preferences: (signal?: AbortSignal) =>
    requestJson<Preferences>("/api/preferences", { signal }),
  savePreference: (modelId: string) =>
    requestJson<Preferences>("/api/preferences", {
      method: "PUT",
      body: JSON.stringify({ defaultTextModelId: modelId }),
    }),
  saveCredential: (providerId: string, apiKey: string) =>
    requestJson<unknown>(
      `/api/providers/${encodeURIComponent(providerId)}/credential`,
      {
        method: "PUT",
        body: JSON.stringify({ apiKey }),
      },
    ),
};
