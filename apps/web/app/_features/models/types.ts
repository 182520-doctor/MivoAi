import type { WorkflowParameter } from "../workflows/types";

export type Model = {
  id: string;
  providerId: string;
  providerName: string;
  name: string;
  modelKey: string;
  capabilities: string[];
  executionMode: string;
  configured: boolean;
  integrationStatus: string;
  kind?: "builtin" | "comfy_workflow";
  workflowId?: string | null;
  parameters?: WorkflowParameter[];
  references?: ModelReference[];
};

export type ModelReference = {
  type: "image" | "video" | "audio" | "file";
  label: string;
  required: boolean;
  min: number;
  max: number;
};

export type Preferences = {
  defaultTextModelId: string | null;
  defaultImageModelId: string | null;
  defaultVideoModelId: string | null;
  agentImageEnabled: boolean;
  agentVideoEnabled: boolean;
};

export type ModelTestResult = {
  success: boolean;
  modelId: string;
  providerId: string;
  latencyMs: number;
  message: string;
  responsePreview: string;
};
