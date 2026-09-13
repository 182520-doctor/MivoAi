import { requestJson } from "../../../shared/api/http";

export type CreativeWorkflowStep = {
  id: string;
  stepKey: string;
  title: string;
  status: string;
  sortOrder: number;
  artifactKind?: string;
  artifactPath?: string;
  summary: string;
};

export type CreativeWorkflow = {
  id: string;
  projectId: string;
  workflowKey: string;
  status: string;
  currentStepKey?: string;
  steps: CreativeWorkflowStep[];
};

export type CreativeProject = {
  id: string;
  sessionId?: string;
  title: string;
  domain: string;
  status: string;
  workspacePath: string;
  spec: {
    idea?: string;
    targetWords?: number;
    chapterCount?: number;
  };
  workflow?: CreativeWorkflow;
};

export type NovelProjectInput = {
  title?: string;
  idea: string;
  targetWords: number;
  chapterCount: number;
  sessionId?: string | null;
};

export const creativeProjectsApi = {
  list: (signal?: AbortSignal) =>
    requestJson<CreativeProject[]>("/api/creative-projects", { signal }),
  createNovel: (input: NovelProjectInput, signal?: AbortSignal) =>
    requestJson<CreativeProject>("/api/creative-projects/novel", {
      method: "POST",
      body: JSON.stringify(input),
      signal,
    }),
};
