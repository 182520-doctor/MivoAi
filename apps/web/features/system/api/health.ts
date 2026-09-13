import { requestJson } from "../../../shared/api/http";

export type Health = {
  status: "ok" | "degraded";
  app_server: {
    running: boolean;
    authenticated: boolean;
    version: string | null;
    platform: string | null;
  };
};

export const readHealth = (signal?: AbortSignal) =>
  requestJson<Health>("/api/status", { signal });
