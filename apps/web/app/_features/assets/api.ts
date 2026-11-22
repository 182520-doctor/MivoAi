import { getJson, requireJson } from "../../_shared/api/client";
import type { AssetLibraryResponse } from "./types";

export function loadAssets(limit = 200) {
  return getJson<AssetLibraryResponse>(`/api/assets?limit=${limit}`);
}

export async function uploadAssets(files: File[]) {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return requireJson<{ assetIds: string[] }>(
    await fetch("/api/assets/upload", {
      method: "POST",
      body,
    }),
  );
}
