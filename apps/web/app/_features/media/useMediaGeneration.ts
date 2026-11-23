"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Model } from "../models/types";
import type { Preferences } from "../models/types";
import { createMediaTask, pollMediaTask, uploadMediaAssets } from "./api";
import type { MediaTask } from "./types";

type GenerationMode = "image" | "video" | "audio";

export function useMediaGeneration(
  models: Model[],
  preferences: Preferences | null = null,
) {
  const [mode, setMode] = useState<GenerationMode>("image");
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [count, setCount] = useState(1);
  const [task, setTask] = useState<MediaTask | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [parameterValues, setParameterValues] = useState<
    Record<string, unknown>
  >({});
  const [assetIdsByParameter, setAssetIdsByParameter] = useState<
    Record<string, string[]>
  >({});
  const [uploadingAssets, setUploadingAssets] = useState(false);
  const [selectedByMode, setSelectedByMode] = useState<
    Partial<Record<GenerationMode, string>>
  >({});
  const abortRef = useRef<AbortController | null>(null);

  const availableModels = useMemo(
    () =>
      models.filter((item) =>
        mode === "image"
          ? item.capabilities.some((capability) =>
              ["image_generation", "image_processing"].includes(capability),
            )
          : mode === "video"
            ? item.capabilities.some((capability) =>
                ["video_generation", "video_processing"].includes(
                  capability,
                ),
              )
            : item.capabilities.includes("audio_processing"),
      ),
    [mode, models],
  );
  const selectedModelId =
    selectedByMode[mode] ?? availableModels[0]?.id ?? "";
  const model = availableModels.find((item) => item.id === selectedModelId);
  const parameterSchema = model?.parameters ?? [];
  const promptParameter = parameterSchema.find(isPromptParameter);
  const formParameters = useMemo(
    () =>
      parameterSchema.filter(
        (parameter) =>
          !isPromptParameter(parameter) && !parameter.derived,
      ),
    [parameterSchema],
  );
  const referenceInputs = useMemo(() => model?.references ?? [], [model]);
  const assetIds = useMemo(
    () => Object.values(assetIdsByParameter).flat(),
    [assetIdsByParameter],
  );
  const promptRequired =
    model?.kind !== "comfy_workflow" ||
    Boolean(promptParameter?.required);

  useEffect(() => {
    const preferred =
      mode === "image"
        ? preferences?.defaultImageModelId
        : mode === "video"
          ? preferences?.defaultVideoModelId
          : undefined;
    if (
      availableModels.length &&
      !availableModels.some((item) => item.id === selectedByMode[mode])
    ) {
      setSelectedByMode((current) => ({
        ...current,
        [mode]:
          (preferred &&
          availableModels.some((item) => item.id === preferred)
            ? preferred
            : availableModels[0].id),
      }));
    }
  }, [availableModels, mode, preferences, selectedByMode]);

  useEffect(() => {
    setParameterValues(
      Object.fromEntries(
        formParameters
          .filter((parameter) => parameter.type !== "assets")
          .map((parameter) => [parameter.key, parameter.default ?? ""]),
      ),
    );
    setAssetIdsByParameter({});
  }, [model?.id, formParameters]);

  async function generate() {
    if ((promptRequired && !prompt.trim()) || !model || isSubmitting) return;
    setError("");
    setTask(null);
    setIsSubmitting(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const { width, height } = dimensionsFor(aspectRatio, mode);
    const images = assetIdsByParameter.image ?? [];
    const videos = assetIdsByParameter.video ?? [];
    const audios = assetIdsByParameter.audio ?? [];
    const files = assetIdsByParameter.file ?? [];
    try {
      const created = await createMediaTask({
        providerId: model.providerId,
        modelId: model.id,
        taskType:
          mode === "image"
            ? model.capabilities.includes("image_processing")
              ? "image_processing"
              : "image_generation"
            : mode === "video"
              ? model.capabilities.includes("video_processing")
                ? "video_processing"
                : "video_generation"
              : "audio_processing",
        prompt: prompt.trim(),
        inputAssetIds: images,
        images,
        videos,
        audios,
        files,
        parameters: parameterSchema.length
          ? {
              ...parameterValues,
              ...(promptParameter
                ? { [promptParameter.key]: prompt.trim() }
                : { prompt: prompt.trim() }),
            }
          : mode === "image"
            && model.capabilities.includes("image_processing")
            ? {}
            : mode === "image"
            ? { width, height, count, steps: 12, guidance: 3.5, seed: null }
            : mode === "video"
              ? {
                width: Math.min(width, 512),
                height: Math.min(height, 512),
                length: 17,
                fps: 12,
                steps: 12,
                seed: null,
                }
              : {},
        clientRequestId: crypto.randomUUID(),
      });
      setTask(created);
      const completed = await pollMediaTask(created.id, setTask, controller.signal);
      if (completed.status === "failed") {
        setError(completed.errorMessage || "ComfyUI 生成失败");
      }
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        setError((caught as Error).message);
      }
    } finally {
      setIsSubmitting(false);
      abortRef.current = null;
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setIsSubmitting(false);
    setError("已停止等待任务；ComfyUI 中的执行可能仍会继续。");
  }

  async function uploadAssets(parameterKey: string, files: File[]) {
    if (!files.length) return;
    setUploadingAssets(true);
    setError("");
    try {
      const uploaded = await uploadMediaAssets(files);
      setAssetIdsByParameter((current) => ({
        ...current,
        [parameterKey]: [
          ...(current[parameterKey] ?? []),
          ...uploaded.assetIds,
        ],
      }));
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setUploadingAssets(false);
    }
  }

  function removeAsset(parameterKey: string, assetId: string) {
    setAssetIdsByParameter((current) => ({
      ...current,
      [parameterKey]: (current[parameterKey] ?? []).filter(
        (item) => item !== assetId,
      ),
    }));
  }

  return {
    mode,
    setMode,
    prompt,
    promptRequired,
    setPrompt,
    aspectRatio,
    setAspectRatio,
    count,
    setCount,
    availableModels,
    selectedModelId,
    setSelectedModelId: (modelId: string) =>
      setSelectedByMode((current) => ({ ...current, [mode]: modelId })),
    model,
    parameterSchema,
    formParameters,
    referenceInputs,
    parameterValues,
    setParameter: (key: string, value: unknown) =>
      setParameterValues((current) => ({ ...current, [key]: value })),
    assetIds,
    assetIdsByParameter,
    uploadingAssets,
    uploadAssets,
    removeAsset,
    task,
    error,
    isSubmitting,
    generate,
    cancel,
  };
}

function dimensionsFor(aspectRatio: string, mode: GenerationMode) {
  const base = mode === "video" ? 512 : 1024;
  if (aspectRatio === "9:16") {
    return { width: Math.round(base * 0.75), height: base };
  }
  if (aspectRatio === "1:1") {
    return { width: base, height: base };
  }
  return { width: base, height: Math.round(base * 0.5625) };
}

function isPromptParameter(parameter: {
  key: string;
  label?: string;
}) {
  const text = `${parameter.key} ${parameter.label ?? ""}`.toLowerCase();
  return (
    parameter.key === "prompt" ||
    text.includes("提示词") ||
    text.includes("prompt")
  );
}
