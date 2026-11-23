"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createDramaProject,
  loadDramaProjects,
  updateDramaProjectStage,
} from "./api";
import type { CreateDramaProjectInput, DramaProject } from "./types";

export function useDramaProjects() {
  const [projects, setProjects] = useState<DramaProject[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setNotice("");
    try {
      const data = await loadDramaProjects();
      setProjects(data);
      setSelectedId((current) => {
        const saved = localStorage.getItem("mivo-drama-project");
        const preferred = current || saved;
        if (preferred && data.some((project) => project.id === preferred)) {
          return preferred;
        }
        return data[0]?.id ?? null;
      });
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function selectProject(projectId: string | null) {
    setSelectedId(projectId);
    if (projectId) {
      localStorage.setItem("mivo-drama-project", projectId);
    } else {
      localStorage.removeItem("mivo-drama-project");
    }
  }

  async function create(input: CreateDramaProjectInput) {
    setSaving(true);
    setNotice("");
    try {
      const project = await createDramaProject(input);
      setProjects((current) => [project, ...current]);
      selectProject(project.id);
      return project;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function updateStage(projectId: string, activeStage: string) {
    setProjects((current) =>
      current.map((project) =>
        project.id === projectId
          ? { ...project, activeStage, status: "in_progress" }
          : project,
      ),
    );
    try {
      const updated = await updateDramaProjectStage(
        projectId,
        activeStage,
        "in_progress",
      );
      setProjects((current) =>
        current.map((project) =>
          project.id === projectId ? updated : project,
        ),
      );
    } catch (error) {
      setNotice((error as Error).message);
      await refresh();
    }
  }

  return {
    projects,
    project:
      projects.find((project) => project.id === selectedId) ?? null,
    selectedId,
    loading,
    saving,
    notice,
    refresh,
    create,
    selectProject,
    updateStage,
  };
}
