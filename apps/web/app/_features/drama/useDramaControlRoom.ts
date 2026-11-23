"use client";

import { useCallback, useEffect, useState } from "react";
import {
  decideDramaStage,
  loadDramaControlRoom,
} from "./api";
import type { DramaControlRoom } from "./types";

export function useDramaControlRoom(projectId: string | null) {
  const [controlRoom, setControlRoom] = useState<DramaControlRoom | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!projectId) {
      setControlRoom(null);
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      setControlRoom(await loadDramaControlRoom(projectId));
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function decide(
    stage: string,
    approved: boolean,
    feedback = "",
  ) {
    if (!projectId) return null;
    setSaving(true);
    setNotice("");
    try {
      await decideDramaStage(projectId, stage, approved, feedback);
      await refresh();
      return true;
    } catch (error) {
      setNotice((error as Error).message);
      return false;
    } finally {
      setSaving(false);
    }
  }

  return {
    controlRoom,
    loading,
    saving,
    notice,
    refresh,
    approve: (stage: string, feedback = "") =>
      decide(stage, true, feedback),
    requestChanges: (stage: string, feedback: string) =>
      decide(stage, false, feedback),
  };
}
