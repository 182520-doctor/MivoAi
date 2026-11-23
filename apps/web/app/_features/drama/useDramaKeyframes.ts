"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Model } from "../models/types";
import {
  createMediaTask,
  pollMediaTask,
} from "../media/api";
import { saveDramaShotPrompt } from "./api";
import type { MediaTask } from "../media/types";
import type {
  DramaEntity,
  DramaSceneContract,
  DramaShot,
} from "./types";

type KeyframeShot = DramaShot & {
  episodeTitle: string;
  sceneHeading: string;
  sceneContract?: DramaSceneContract;
};

type UseDramaKeyframesOptions = {
  models: Model[];
  preferredModelId?: string | null;
  shots: KeyframeShot[];
  entities: DramaEntity[];
  initialShotId?: string | null;
  attachShotAssets: (
    shotId: string,
    input: {
      status?: DramaShot["status"];
      firstFrameAssetId?: string;
      lastFrameAssetId?: string;
      grid9AssetId?: string;
      storyboardAssetId?: string;
    },
  ) => Promise<DramaShot | null>;
};

type KeyframeOutputSlot = "first" | "last" | "grid9" | "storyboard";

export function useDramaKeyframes({
  models,
  preferredModelId,
  shots,
  entities,
  initialShotId,
  attachShotAssets,
}: UseDramaKeyframesOptions) {
  const [activeShotId, setActiveShotId] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [outputSlot, setOutputSlot] =
    useState<KeyframeOutputSlot>("first");
  const [prompt, setPrompt] = useState("");
  const [task, setTask] = useState<MediaTask | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const initialShotAppliedRef = useRef<string | null>(null);

  const activeShot =
    shots.find((shot) => shot.id === activeShotId) ?? shots[0] ?? null;
  const referencedEntities = useMemo(() => {
    const ids = new Set(
      activeShot?.entityReferences?.map((reference) => reference.entityId) ??
        [],
    );
    return entities.filter((entity) => ids.has(entity.id));
  }, [activeShot, entities]);
  const referencedEntityKey = referencedEntities
    .map((entity) => entity.id)
    .join("|");
  const referenceAssets = useMemo(() => {
    const ids = referencedEntities.flatMap((entity) => [
      ...(entity.primaryAssetId ? [entity.primaryAssetId] : []),
      ...entity.referenceAssetIds,
    ]);
    return Array.from(new Set(ids));
  }, [referencedEntities]);
  const imageModels = useMemo(
    () =>
      models.filter(
        (model) =>
          model.capabilities.includes("image_generation") &&
          model.integrationStatus === "ready" &&
          model.configured,
      ),
    [models],
  );
  const recommendedModel = useMemo(
    () =>
      selectImageModel(
        imageModels,
        referenceAssets.length,
        preferredModelId,
      ),
    [imageModels, preferredModelId, referenceAssets.length],
  );
  const selectedModel =
    imageModels.find((model) => model.id === selectedModelId) ??
    recommendedModel;
  const imageLimit = imageLimitFor(selectedModel);
  const inputAssetIds = referenceAssets.slice(0, imageLimit);
  const minimumImages = imageMinimumFor(selectedModel);
  const missingRequiredParameters = (
    selectedModel?.parameters ?? []
  ).filter(
    (parameter) =>
      parameter.type !== "assets" &&
      !parameter.derived &&
      parameter.required &&
      parameter.semanticKey !== "prompt" &&
      parameter.default == null,
  );

  useEffect(() => {
    if (
      initialShotId
      && initialShotId !== initialShotAppliedRef.current
      && shots.some((shot) => shot.id === initialShotId)
    ) {
      initialShotAppliedRef.current = initialShotId;
      setActiveShotId(initialShotId);
      return;
    }
    if (activeShotId && shots.some((shot) => shot.id === activeShotId)) {
      return;
    }
    setActiveShotId(shots[0]?.id ?? null);
  }, [activeShotId, initialShotId, shots]);

  useEffect(() => {
    if (recommendedModel?.id) {
      setSelectedModelId(recommendedModel.id);
    }
  }, [recommendedModel?.id, activeShot?.id]);

  useEffect(() => {
    if (!activeShot) {
      setPrompt("");
      return;
    }
    const slot = keyframePromptSlot(outputSlot);
    setPrompt(
      activeShot.promptOverrides?.[slot] ??
        buildKeyframePrompt(activeShot, referencedEntities, outputSlot),
    );
    setTask(null);
    setError("");
  }, [
    activeShot?.id,
    activeShot?.direction,
    activeShot?.sceneContract,
    activeShot?.promptOverrides,
    outputSlot,
    referencedEntityKey,
  ]);

  async function savePrompt() {
    if (!activeShot) return null;
    return saveDramaShotPrompt(
      activeShot.id,
      keyframePromptSlot(outputSlot),
      prompt,
    );
  }

  async function generate() {
    if (!activeShot || !selectedModel || submitting) return;
    if (inputAssetIds.length < minimumImages) {
      setError(
        `当前工作流至少需要 ${minimumImages} 张参考图，镜头只关联了 ${inputAssetIds.length} 张。`,
      );
      return;
    }
    if (missingRequiredParameters.length) {
      setError(
        `工作流缺少默认参数：${missingRequiredParameters
          .map((parameter) => parameter.label)
          .join("、")}`,
      );
      return;
    }
    setSubmitting(true);
    setError("");
    setTask(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await savePrompt();
      const parameters = Object.fromEntries(
        (selectedModel.parameters ?? [])
          .filter(
            (parameter) =>
              parameter.type !== "assets" &&
              !parameter.derived &&
              parameter.default !== undefined,
          )
          .map((parameter) => [parameter.key, parameter.default]),
      );
      const promptKey =
        selectedModel.parameters?.find(
          (parameter) =>
            parameter.semanticKey === "prompt" ||
            parameter.key === "prompt",
        )?.key ?? "prompt";
      const created = await createMediaTask({
        providerId: selectedModel.providerId,
        modelId: selectedModel.id,
        taskType: "image_generation",
        prompt: prompt.trim(),
        inputAssetIds,
        images: inputAssetIds,
        videos: [],
        audios: [],
        files: [],
        parameters: {
          ...parameters,
          [promptKey]: prompt.trim(),
        },
        clientRequestId: crypto.randomUUID(),
      });
      setTask(created);
      const completed = await pollMediaTask(
        created.id,
        setTask,
        controller.signal,
      );
      if (completed.status === "failed") {
        setError(completed.errorMessage || "关键帧生成失败");
        return;
      }
      const assetId = completed.resultAssetIds[0];
      if (assetId) {
        await attachShotAssets(
          activeShot.id,
          outputSlot === "first"
            ? {
                firstFrameAssetId: assetId,
                status: "keyframe_ready",
              }
            : outputSlot === "last"
              ? { lastFrameAssetId: assetId }
              : outputSlot === "grid9"
                ? { grid9AssetId: assetId }
                : { storyboardAssetId: assetId },
        );
      }
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        setError((caught as Error).message);
      }
    } finally {
      setSubmitting(false);
      abortRef.current = null;
    }
  }

  async function attachCandidate(
    assetId: string,
    slot: KeyframeOutputSlot,
  ) {
    if (!activeShot) return;
    await attachShotAssets(
      activeShot.id,
      slot === "first"
        ? {
            firstFrameAssetId: assetId,
            status: "keyframe_ready",
          }
        : slot === "last"
          ? { lastFrameAssetId: assetId }
          : slot === "grid9"
            ? { grid9AssetId: assetId }
            : { storyboardAssetId: assetId },
    );
  }

  function cancel() {
    abortRef.current?.abort();
    setSubmitting(false);
    setError("已停止等待；ComfyUI 队列中的任务可能仍在执行。");
  }

  return {
    activeShot,
    setActiveShotId,
    referencedEntities,
    referenceAssets,
    imageModels,
    selectedModel,
    selectedModelId: selectedModel?.id ?? "",
    setSelectedModelId,
    outputSlot,
    setOutputSlot,
    imageLimit,
    minimumImages,
    missingRequiredParameters,
    prompt,
    setPrompt,
    task,
    error,
    submitting,
    generate,
    cancel,
    attachCandidate,
    savePrompt,
  };
}

function keyframePromptSlot(
  slot: KeyframeOutputSlot,
) {
  return slot === "first" ? "first_frame" : slot === "last" ? "last_frame" : slot;
}

function imageLimitFor(model: Model | undefined) {
  const image = model?.references?.find(
    (reference) => reference.type === "image",
  );
  return image?.max ?? 10;
}

function imageMinimumFor(model: Model | undefined) {
  return (
    model?.references?.find((reference) => reference.type === "image")
      ?.min ?? 0
  );
}

function selectImageModel(
  models: Model[],
  imageCount: number,
  preferredModelId?: string | null,
) {
  const compatible = models.filter((model) => {
    const min = imageMinimumFor(model);
    const max = imageLimitFor(model);
    return imageCount >= min && imageCount <= max;
  });
  const preferred = compatible.find(
    (model) => model.id === preferredModelId,
  );
  if (preferred) return preferred;
  return compatible.sort((left, right) => {
    const leftMax = imageLimitFor(left);
    const rightMax = imageLimitFor(right);
    if (imageCount === 0) {
      return leftMax - rightMax;
    }
    return rightMax - leftMax;
  })[0] ?? models[0];
}

function buildKeyframePrompt(
  shot: KeyframeShot,
  entities: DramaEntity[],
  outputSlot: KeyframeOutputSlot,
) {
  const targetInstruction: Record<KeyframeOutputSlot, string> = {
    first:
      "生成镜头首帧：动作开始前的稳定画面，为后续视频提供准确起点。",
    last:
      "生成镜头尾帧：动作结束后的稳定画面，人物位置、姿态、表情、服装、场景和道具必须能自然接续首帧。",
    grid9:
      "生成九宫格连续帧：3×3 九格按从左到右、从上到下的顺序展示同一镜头从开始到结束的连续动作，人物身份、服装、场景、光线和道具保持完全一致。每格是同一镜头的连续时间采样，不是不同场景拼贴。",
    storyboard:
      "生成电影故事板：用六到九个分格完整描述同一镜头的起幅、动作发展、转折、落幅和机位景别变化，分格顺序清楚，人物与空间保持连续，不添加文字或标注框。",
  };
  const contract = shot.sceneContract;
  const direction = shot.direction;
  const directionContext = [
    direction.shotSize ? `景别：${direction.shotSize}。` : "",
    direction.cameraAngle ? `机位角度：${direction.cameraAngle}。` : "",
    direction.cameraMovement
      ? `镜头运动：${direction.cameraMovement}。`
      : "",
    direction.lens ? `镜头焦段：${direction.lens}。` : "",
    direction.blocking ? `人物调度：${direction.blocking}。` : "",
    direction.performanceAction
      ? `表演动作：${direction.performanceAction}。`
      : "",
    direction.expression ? `表情：${direction.expression}。` : "",
    direction.composition ? `构图：${direction.composition}。` : "",
    direction.lighting ? `灯光：${direction.lighting}。` : "",
    direction.sound ? `声音：${direction.sound}。` : "",
    direction.referenceNotes
      ? `参考说明：${direction.referenceNotes}。`
      : "",
  ].filter(Boolean);
  const dramaticContext = contract
    ? [
        `场次创作任务：从“${contract.valueIn || "起始状态"}”转向“${
          contract.valueOut || "结束状态"
        }”。`,
        contract.characterObjectives.length
          ? `人物目标：${contract.characterObjectives.join("；")}。`
          : "",
        contract.obstacle ? `障碍：${contract.obstacle}。` : "",
        contract.turn ? `关键转折：${contract.turn}。` : "",
        contract.subtext ? `潜台词：${contract.subtext}。` : "",
        contract.performanceNotes
          ? `声台形表：${contract.performanceNotes}。`
          : "",
        contract.visualStrategy
          ? `视觉策略：${contract.visualStrategy}。`
          : "",
      ]
    : [];
  return [
    `电影分镜画面，${shot.title}。`,
    targetInstruction[outputSlot],
    ...directionContext,
    ...dramaticContext,
    shot.description || "根据剧本描述建立清晰的画面动作与构图。",
    shot.dialogue ? `对白：${shot.dialogue}` : "",
    entities.length
      ? `角色与场景连续性：${entities
          .map(
            (entity) =>
              `${entity.name}（${entity.description || "保持参考图特征"}）`,
          )
          .join("；")}。`
      : "",
    "保持人物身份、服装、场景、光线与道具一致；构图清楚，为后续首尾帧视频预留稳定空间。",
  ]
    .filter(Boolean)
    .join("\n");
}
