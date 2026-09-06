"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../../shared/api/http";
import { modelsApi } from "../api/models";
import type { Model } from "../types";

export function useModelSettings() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedId, setSelectedId] = useState("codex-local-default");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async (signal?: AbortSignal) => {
    const [models, preferences] = await Promise.all([
      modelsApi.list(signal),
      modelsApi.preferences(signal),
    ]);
    if (signal?.aborted) return;
    setModels(models);
    setSelectedId(preferences.defaultTextModelId ?? "codex-local-default");
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    reload(controller.signal)
      .catch((error) => {
        if (!controller.signal.aborted) setNotice(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);

  async function selectModel(id: string) {
    setSaving(true);
    setNotice("");
    try {
      await modelsApi.savePreference(id);
      setSelectedId(id);
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function saveKey(key: string): Promise<boolean> {
    setSaving(true);
    setNotice("");
    try {
      await modelsApi.saveCredential("volcengine", key);
      await reload();
      setNotice("密钥已保存");
      return true;
    } catch (error) {
      setNotice(errorMessage(error));
      return false;
    } finally {
      setSaving(false);
    }
  }

  return {
    models,
    selectedId,
    selectedModel: models.find((model) => model.id === selectedId),
    loading,
    saving,
    notice,
    selectModel,
    saveKey,
  };
}
