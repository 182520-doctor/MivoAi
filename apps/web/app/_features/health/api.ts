import { getJson } from "../../_shared/api/client";
import type { Health } from "./types";

export function loadHealth(signal?: AbortSignal) {
  return getJson<Health>("/api/status", signal);
}
