export type TaskCenterItem = {
  id: string;
  sessionId: string | null;
  providerId: string;
  providerName: string;
  modelId: string;
  modelName: string;
  taskType: string;
  prompt: string;
  status: string;
  progress: number | null;
  providerTaskId: string | null;
  resultAssetIds: string[];
  errorMessage: string | null;
  origin: {
    kind?: string;
    projectId?: string;
    episodeId?: string;
    productionRunId?: string;
    stage?: string;
    targetType?: string;
    targetId?: string;
    slot?: string;
  } | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
};

export type TaskCenterResponse = {
  tasks: TaskCenterItem[];
  summary: Record<string, number>;
};
