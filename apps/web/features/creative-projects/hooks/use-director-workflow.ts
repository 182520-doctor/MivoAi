"use client";

import { useState } from "react";
import { errorMessage } from "../../../shared/api/http";
import {
  creativeProjectsApi,
  type CreativeProject,
} from "../api/creative-projects";

type CreateNovelInput = {
  idea: string;
  chapterCount: number;
  targetWords: number;
  sessionId: string | null;
};

export function useDirectorWorkflow(
  onPromptReady: (prompt: string, projectId: string) => Promise<void>,
) {
  const [project, setProject] = useState<CreativeProject | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function createNovelProject(input: CreateNovelInput) {
    if (!input.idea.trim() || loading) return;
    setLoading(true);
    setNotice("");
    try {
      const created = await creativeProjectsApi.createNovel({
        idea: input.idea,
        title: titleFromIdea(input.idea),
        chapterCount: input.chapterCount,
        targetWords: input.targetWords,
        sessionId: input.sessionId,
      });
      setProject(created);
      await onPromptReady(input.idea.trim(), created.id);
      setNotice("小说项目已创建，Agent 已开始自动创作。");
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return { project, notice, loading, createNovelProject };
}

function titleFromIdea(idea: string) {
  return idea.trim().replace(/\s+/g, "").slice(0, 18) || "新的小说项目";
}
