import { getJson, requireJson } from "../../_shared/api/client";
import type { TaskCenterItem, TaskCenterResponse } from "./types";

export function loadTaskCenter(limit = 200) {
  return getJson<TaskCenterResponse>(`/api/generations?limit=${limit}`);
}

export async function retryMediaTask(taskId: string) {
  return requireJson<TaskCenterItem>(
    await fetch(`/api/generations/${taskId}/retry`, {
      method: "POST",
    }),
  );
}

export async function retryMediaTasks(taskIds: string[]) {
  return requireJson<{
    tasks: TaskCenterItem[];
    failures: Array<{ taskId: string; error: string }>;
  }>(
    await fetch("/api/generations/retry-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ taskIds }),
    }),
  );
}
