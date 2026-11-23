"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  loadModelCatalog,
  saveModelPreferences,
  saveProviderKey,
} from "./api";
import type { Model, Preferences } from "./types";

export function useModelSettings() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("codex-local-default");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [settingsNotice, setSettingsNotice] = useState("");
  const [preferences, setPreferences] = useState<Preferences | null>(null);

  const loadSettings = useCallback(async () => {
    try {
      const { models: nextModels, preferences } = await loadModelCatalog();
      setModels(nextModels);
      setPreferences(preferences);
      if (preferences.defaultTextModelId) {
        setSelectedModelId(preferences.defaultTextModelId);
      }
    } catch {
      setSettingsNotice("无法加载模型目录");
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId),
    [models, selectedModelId],
  );

  async function selectModel(modelId: string) {
    setSelectedModelId(modelId);
    try {
      const next = await saveModelPreferences({
        ...preferenceDefaults(preferences),
        defaultTextModelId: modelId,
      });
      setPreferences(next);
      setSettingsNotice("");
    } catch {
      setSettingsNotice("保存默认模型失败");
    }
  }

  async function selectMediaModel(
    modelId: string,
    kind: "image" | "video",
  ) {
    try {
      const next = await saveModelPreferences({
        ...preferenceDefaults(preferences),
        ...(kind === "image"
          ? { defaultImageModelId: modelId }
          : { defaultVideoModelId: modelId }),
      });
      setPreferences(next);
      setSettingsNotice(
        kind === "image" ? "默认图片模型已更新" : "默认视频模型已更新",
      );
    } catch {
      setSettingsNotice("保存媒体模型偏好失败");
    }
  }

  async function saveVolcengineKey() {
    setSettingsNotice("");
    try {
      await saveProviderKey("volcengine", apiKey);
      setApiKey("");
      setSettingsNotice("已保存，Key 不会返回到浏览器");
      await loadSettings();
    } catch {
      setSettingsNotice("保存火山引擎 API Key 失败");
    }
  }

  function canUseSelectedModel(connected: boolean) {
    if (selectedModel?.providerId === "volcengine") {
      return Boolean(
        selectedModel.configured && selectedModel.integrationStatus === "ready",
      );
    }
    return connected;
  }

  return {
    models,
    preferences,
    selectedModel,
    selectedModelId,
    settingsOpen,
    setSettingsOpen,
    apiKey,
    setApiKey,
    settingsNotice,
    loadSettings,
    selectModel,
    selectMediaModel,
    saveVolcengineKey,
    canUseSelectedModel,
  };
}

function preferenceDefaults(preferences: Preferences | null) {
  return {
    defaultTextModelId: preferences?.defaultTextModelId ?? null,
    defaultImageModelId: preferences?.defaultImageModelId ?? null,
    defaultVideoModelId: preferences?.defaultVideoModelId ?? null,
    agentImageEnabled: preferences?.agentImageEnabled ?? false,
    agentVideoEnabled: preferences?.agentVideoEnabled ?? false,
  };
}
