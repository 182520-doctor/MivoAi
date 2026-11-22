export type MediaTaskStatus =
  | "pending"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled";

export type MediaTask = {
  id: string;
  sessionId: string | null;
  providerId: string;
  providerName?: string | null;
  modelId: string;
  modelName?: string | null;
  taskType: string;
  prompt: string;
  status: MediaTaskStatus;
  progress: number | null;
  providerTaskId: string | null;
  resultAssetIds: string[];
  resultAssets?: Array<{
    id: string;
    type: string;
    mimeType: string | null;
    size: number | null;
    metadata: Record<string, unknown>;
    url: string;
  }>;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
};

export type MediaGenerationInput = {
  providerId: string;
  modelId: string;
  taskType:
    | "image_generation"
    | "image_processing"
    | "video_generation"
    | "video_processing"
    | "audio_processing"
    | "transcription";
  prompt: string;
  inputAssetIds: string[];
  images: string[];
  videos: string[];
  audios: string[];
  files: string[];
  parameters: Record<string, unknown>;
  clientRequestId: string;
};
