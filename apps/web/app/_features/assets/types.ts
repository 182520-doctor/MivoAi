export type LibraryAsset = {
  id: string;
  type: "image" | "video" | "audio" | "file";
  source: "upload" | "generated" | "remote";
  mimeType: string | null;
  size: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  taskId: string | null;
  sessionId: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  url: string;
};

export type AssetLibraryResponse = {
  assets: LibraryAsset[];
  summary: Record<string, number>;
};
