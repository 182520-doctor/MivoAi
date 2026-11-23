"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createDramaEpisode,
  createDramaScene,
  createDramaShot,
  loadDramaAudit,
  loadDramaProduction,
  renderDramaEpisode,
  saveDramaEpisodePlan,
  saveDramaAudioMix,
  saveDramaSubtitleStyle,
  saveDramaSubtitles,
  updateDramaShot,
  updateDramaShotStatus,
} from "./api";
import type {
  DramaAudit,
  DramaEpisode,
  DramaEpisodePlan,
  DramaAudioMix,
  DramaShot,
  DramaSubtitleCue,
  DramaSubtitleStyle,
} from "./types";

export function useDramaProduction(projectId: string | null) {
  const [episodes, setEpisodes] = useState<DramaEpisode[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [renderingEpisodeId, setRenderingEpisodeId] = useState<string | null>(
    null,
  );
  const [audit, setAudit] = useState<DramaAudit | null>(null);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!projectId) {
      setEpisodes([]);
      setAudit(null);
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const [nextEpisodes, nextAudit] = await Promise.all([
        loadDramaProduction(projectId),
        loadDramaAudit(projectId),
      ]);
      setEpisodes(nextEpisodes);
      setAudit(nextAudit);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function addEpisode(title: string) {
    if (!projectId) return null;
    setSaving(true);
    try {
      const episode = await createDramaEpisode(projectId, title);
      setEpisodes((items) => [...items, { ...episode, scenes: [] }]);
      return episode;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function addScene(episodeId: string, heading: string) {
    setSaving(true);
    try {
      const scene = await createDramaScene(episodeId, heading);
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? {
                ...episode,
                scenes: [...episode.scenes, { ...scene, shots: [] }],
              }
            : episode,
        ),
      );
      return scene;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function updateEpisodePlan(
    episodeId: string,
    plan: DramaEpisodePlan,
  ) {
    setSaving(true);
    setNotice("");
    try {
      const updated = await saveDramaEpisodePlan(episodeId, plan);
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? { ...episode, ...updated, scenes: episode.scenes }
            : episode,
        ),
      );
      return updated;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function addShot(
    sceneId: string,
    input: {
      title: string;
      description?: string;
      dialogue?: string;
      durationSeconds?: number;
    },
  ) {
    setSaving(true);
    try {
      const shot = await createDramaShot(sceneId, input);
      setEpisodes((items) =>
        items.map((episode) => ({
          ...episode,
          scenes: episode.scenes.map((scene) =>
            scene.id === sceneId
              ? { ...scene, shots: [...scene.shots, shot] }
              : scene,
          ),
        })),
      );
      return shot;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function setShotStatus(
    shotId: string,
    status: DramaShot["status"],
  ) {
    try {
      const shot = await updateDramaShotStatus(
        shotId,
        status,
        status === "approved"
          ? "用户通过镜头"
          : status === "clip_ready"
            ? "用户退回复做"
            : "",
      );
      setEpisodes((items) =>
        items.map((episode) => ({
          ...episode,
          scenes: episode.scenes.map((scene) => ({
            ...scene,
            shots: scene.shots.map((item) =>
              item.id === shotId
                ? {
                    ...item,
                    ...shot,
                    entityReferences:
                      shot.entityReferences ?? item.entityReferences,
                  }
                : item,
            ),
          })),
        })),
      );
      return shot;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    }
  }

  async function attachShotAssets(
    shotId: string,
    input: Parameters<typeof updateDramaShot>[1],
  ) {
    try {
      const shot = await updateDramaShot(shotId, input);
      setEpisodes((items) =>
        items.map((episode) => ({
          ...episode,
          scenes: episode.scenes.map((scene) => ({
            ...scene,
            shots: scene.shots.map((item) =>
              item.id === shotId
                ? {
                    ...item,
                    ...shot,
                    entityReferences:
                      shot.entityReferences ?? item.entityReferences,
                  }
                : item,
            ),
          })),
        })),
      );
      return shot;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    }
  }

  async function renderEpisode(
    episodeId: string,
    transition = "none",
    transitionDuration = 0.4,
  ) {
    setRenderingEpisodeId(episodeId);
    setNotice("");
    try {
      const rendered = await renderDramaEpisode(
        episodeId,
        transition,
        transitionDuration,
      );
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? {
                ...episode,
                ...rendered,
                scenes: episode.scenes,
              }
            : episode,
        ),
      );
      void refresh();
      return rendered;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setRenderingEpisodeId(null);
    }
  }

  async function updateSubtitles(
    episodeId: string,
    cues: DramaSubtitleCue[],
  ) {
    try {
      const result = await saveDramaSubtitles(episodeId, cues);
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? { ...episode, subtitleCues: result.cues }
            : episode,
        ),
      );
      return result.cues;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    }
  }

  async function updateAudioMix(
    episodeId: string,
    input: DramaAudioMix,
  ) {
    try {
      const audioMix = await saveDramaAudioMix(episodeId, input);
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? { ...episode, audioMix }
            : episode,
        ),
      );
      return audioMix;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    }
  }

  async function updateSubtitleStyle(
    episodeId: string,
    input: DramaSubtitleStyle,
  ) {
    try {
      const subtitleStyle = await saveDramaSubtitleStyle(
        episodeId,
        input,
      );
      setEpisodes((items) =>
        items.map((episode) =>
          episode.id === episodeId
            ? { ...episode, subtitleStyle }
            : episode,
        ),
      );
      return subtitleStyle;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    }
  }

  return {
    episodes,
    loading,
    saving,
    renderingEpisodeId,
    audit,
    notice,
    refresh,
    addEpisode,
    updateEpisodePlan,
    addScene,
    addShot,
    setShotStatus,
    attachShotAssets,
    renderEpisode,
    updateSubtitles,
    updateAudioMix,
    updateSubtitleStyle,
  };
}
