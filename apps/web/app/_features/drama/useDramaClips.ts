"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Model } from "../models/types";
import {
  createMediaTask,
  pollMediaTask,
} from "../media/api";
import { saveDramaShotPrompt } from "./api";
import { extractVideoAudio } from "../media/processingApi";
import type { MediaTask } from "../media/types";
import type {
  DramaEntity,
  DramaSceneContract,
  DramaShot,
} from "./types";

type ClipShot = DramaShot & {
  episodeTitle: string;
  sceneHeading: string;
  sceneContract?: DramaSceneContract;
};

type AttachShotInput = {
  status?: DramaShot["status"];
  firstFrameAssetId?: string;
  lastFrameAssetId?: string;
  videoAssetId?: string;
  audioAssetId?: string;
};

type UseDramaClipsOptions = {
  models: Model[];
  preferredModelId?: string | null;
  shots: ClipShot[];
  entities: DramaEntity[];
  aspectRatio: string;
  initialShotId?: string | null;
  attachShotAssets: (
    shotId: string,
    input: AttachShotInput,
  ) => Promise<DramaShot | null>;
};

export function useDramaClips({
  models,
  preferredModelId,
  shots,
  entities,
  aspectRatio,
  initialShotId,
  attachShotAssets,
}: UseDramaClipsOptions) {
  const [activeShotId, setActiveShotId] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [task, setTask] = useState<MediaTask | null>(null);
  const [extractTask, setExtractTask] = useState<MediaTask | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [extracting, setExtracting] = useState<
    "first" | "last" | "audio" | null
  >(null);
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
  const sourceImages = useMemo(() => {
    const entityImages = referencedEntities.flatMap((entity) => [
      ...(entity.primaryAssetId ? [entity.primaryAssetId] : []),
      ...entity.referenceAssetIds,
    ]);
    return Array.from(
      new Set(
        [
          activeShot?.firstFrameAssetId,
          activeShot?.lastFrameAssetId,
          activeShot?.grid9AssetId,
          activeShot?.storyboardAssetId,
          ...entityImages,
        ].filter((assetId): assetId is string => Boolean(assetId)),
      ),
    );
  }, [activeShot, referencedEntities]);
  const framePair = useMemo(
    () =>
      activeShot?.firstFrameAssetId &&
      activeShot.lastFrameAssetId &&
      activeShot.firstFrameAssetId !== activeShot.lastFrameAssetId
        ? [activeShot.firstFrameAssetId, activeShot.lastFrameAssetId]
        : null,
    [activeShot?.firstFrameAssetId, activeShot?.lastFrameAssetId],
  );
  const videoModels = useMemo(
    () =>
      models.filter(
        (model) =>
          model.capabilities.includes("video_generation") &&
          model.integrationStatus === "ready" &&
          model.configured,
      ),
    [models],
  );
  const recommendedModel = useMemo(
    () =>
      selectVideoModel(
        videoModels,
        sourceImages.length,
        Boolean(framePair),
        preferredModelId,
      ),
    [framePair, preferredModelId, sourceImages.length, videoModels],
  );
  const selectedModel =
    videoModels.find((model) => model.id === selectedModelId) ??
    recommendedModel;
  const isFrameModel = isFirstLastFrameModel(selectedModel);
  const inputAssetIds = isFrameModel
    ? (framePair ?? []).slice(0, imageLimitFor(selectedModel))
    : sourceImages.slice(0, imageLimitFor(selectedModel));
  const minimumImages = requiredImageMinimum(selectedModel);
  const modelCompatible =
    inputAssetIds.length >= minimumImages &&
    inputAssetIds.length <= imageLimitFor(selectedModel);
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
  const extractionModels = useMemo(
    () =>
      models.filter(
        (model) =>
          model.capabilities.some((capability) =>
            ["image_generation", "image_processing"].includes(capability),
          ) &&
          model.integrationStatus === "ready" &&
          model.configured &&
          model.references?.some(
            (reference) =>
              reference.type === "video" &&
              reference.min === 1 &&
              reference.max === 1,
          ),
      ),
    [models],
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
  }, [activeShot?.id, recommendedModel?.id]);

  useEffect(() => {
    if (!activeShot) {
      setPrompt("");
      return;
    }
    setPrompt(
      activeShot.promptOverrides?.video ??
        buildClipPrompt(
          activeShot,
          referencedEntities,
          Boolean(framePair),
        ),
    );
    setTask(null);
    setExtractTask(null);
    setError("");
  }, [
    activeShot?.id,
    activeShot?.direction,
    activeShot?.sceneContract,
    activeShot?.promptOverrides,
    framePair,
    referencedEntityKey,
  ]);

  async function savePrompt() {
    if (!activeShot) return null;
    return saveDramaShotPrompt(activeShot.id, "video", prompt);
  }

  async function generate() {
    if (!activeShot || !selectedModel || submitting) return;
    if (!modelCompatible) {
      setError(renderCompatibilityError(selectedModel, inputAssetIds.length));
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
      const parameters = buildVideoParameters(
        selectedModel,
        aspectRatio,
        activeShot.durationSeconds,
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
        taskType: "video_generation",
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
        setError(completed.errorMessage || "镜头视频生成失败");
        return;
      }
      const videoAssetId = completed.resultAssetIds[0];
      if (videoAssetId) {
        await attachShotAssets(activeShot.id, {
          videoAssetId,
          status: "clip_ready",
        });
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

  async function attachVideo(assetId: string) {
    if (!activeShot) return;
    await attachShotAssets(activeShot.id, {
      videoAssetId: assetId,
      status: "clip_ready",
    });
  }

  async function extractFrame(slot: "first" | "last") {
    if (!activeShot?.videoAssetId || extracting) return;
    const model = extractionModels.find((item) =>
      item.name.includes(slot === "first" ? "首帧" : "尾帧"),
    );
    if (!model) {
      setError(`没有可用的视频${slot === "first" ? "首帧" : "尾帧"}提取工作流`);
      return;
    }
    setExtracting(slot);
    setError("");
    setExtractTask(null);
    try {
      const created = await createMediaTask({
        providerId: model.providerId,
        modelId: model.id,
        taskType: model.capabilities.includes("image_processing")
          ? "image_processing"
          : "image_generation",
        prompt: "",
        inputAssetIds: [],
        images: [],
        videos: [activeShot.videoAssetId],
        audios: [],
        files: [],
        parameters: {},
        clientRequestId: crypto.randomUUID(),
      });
      setExtractTask(created);
      const controller = new AbortController();
      abortRef.current = controller;
      const completed = await pollMediaTask(
        created.id,
        setExtractTask,
        controller.signal,
      );
      if (completed.status === "failed") {
        setError(completed.errorMessage || "视频抽帧失败");
        return;
      }
      const frameAssetId = completed.resultAssetIds[0];
      if (frameAssetId) {
        await attachShotAssets(
          activeShot.id,
          slot === "first"
            ? {
                firstFrameAssetId: frameAssetId,
                status: "clip_ready",
              }
            : {
                lastFrameAssetId: frameAssetId,
                status: "clip_ready",
              },
        );
      }
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        setError((caught as Error).message);
      }
    } finally {
      setExtracting(null);
      abortRef.current = null;
    }
  }

  async function extractAudio() {
    if (!activeShot?.videoAssetId || extracting) return;
    setExtracting("audio");
    setError("");
    try {
      const result = await extractVideoAudio(activeShot.videoAssetId);
      await attachShotAssets(activeShot.id, {
        audioAssetId: result.assetId,
      });
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setExtracting(null);
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setSubmitting(false);
    setExtracting(null);
    setError("已停止等待；ComfyUI 队列中的任务可能仍在执行。");
  }

  return {
    activeShot,
    setActiveShotId,
    referencedEntities,
    sourceImages,
    framePair,
    videoModels,
    selectedModel,
    selectedModelId: selectedModel?.id ?? "",
    setSelectedModelId,
    modelCompatible,
    minimumImages,
    imageLimit: imageLimitFor(selectedModel),
    missingRequiredParameters,
    modelReason: videoModelReason(selectedModel, Boolean(framePair)),
    prompt,
    setPrompt,
    task,
    extractTask,
    error,
    submitting,
    extracting,
    generate,
    attachVideo,
    savePrompt,
    extractFrame,
    extractAudio,
    cancel,
    canExtractFirst: extractionModels.some((model) =>
      model.name.includes("首帧"),
    ),
    canExtractLast: extractionModels.some((model) =>
      model.name.includes("尾帧"),
    ),
  };
}

function imageLimitFor(model: Model | undefined) {
  return (
    model?.references?.find((reference) => reference.type === "image")
      ?.max ?? 0
  );
}

function imageMinimumFor(model: Model | undefined) {
  return (
    model?.references?.find((reference) => reference.type === "image")
      ?.min ?? 0
  );
}

function requiredImageMinimum(model: Model | undefined) {
  const declared = imageMinimumFor(model);
  if (declared > 0) return declared;
  if (
    model?.name.includes("多参考") &&
    (model.references?.some(
      (reference) => reference.type === "image" && reference.max > 0,
    ) ??
      false)
  ) {
    return 1;
  }
  return 0;
}

function isFirstLastFrameModel(model: Model | undefined) {
  const image = model?.references?.find(
    (reference) => reference.type === "image",
  );
  return Boolean(
    image?.min === 2 &&
      image.max === 2 &&
      (model?.name.includes("首尾") ||
        model?.name.toLowerCase().includes("flf")),
  );
}

function selectVideoModel(
  models: Model[],
  imageCount: number,
  hasFramePair: boolean,
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
  if (preferred && (!hasFramePair || isFirstLastFrameModel(preferred))) {
    return preferred;
  }
  if (hasFramePair) {
    const frameModel = compatible.find(isFirstLastFrameModel);
    if (frameModel) return frameModel;
  }
  return compatible.sort((left, right) => {
    const leftName = left.name;
    const rightName = right.name;
    const leftScore =
      (imageCount > 0 && leftName.includes("多参考") ? 4 : 0) +
      (imageCount === 0 && leftName.includes("文生视频") ? 4 : 0) +
      (left.kind === "comfy_workflow" ? 2 : 0);
    const rightScore =
      (imageCount > 0 && rightName.includes("多参考") ? 4 : 0) +
      (imageCount === 0 && rightName.includes("文生视频") ? 4 : 0) +
      (right.kind === "comfy_workflow" ? 2 : 0);
    return rightScore - leftScore;
  })[0] ?? models[0];
}

function buildVideoParameters(
  model: Model,
  aspectRatio: string,
  durationSeconds: number,
) {
  const values = Object.fromEntries(
    (model.parameters ?? [])
      .filter(
        (parameter) =>
          parameter.type !== "assets" &&
          !parameter.derived &&
          parameter.default !== undefined,
      )
      .map((parameter) => [parameter.key, parameter.default]),
  ) as Record<string, unknown>;
  const aspectParameter = model.parameters?.find(
    (parameter) => parameter.semanticKey === "aspectRatio",
  );
  if (
    aspectParameter &&
    (!aspectParameter.options?.length ||
      aspectParameter.options.map(String).includes(aspectRatio))
  ) {
    values[aspectParameter.key] = aspectRatio;
  }
  const durationParameter = model.parameters?.find(
    (parameter) =>
      parameter.semanticKey === "duration" ||
      parameter.key === "duration",
  );
  if (durationParameter) {
    values[durationParameter.key] = durationSeconds;
  }
  return values;
}

function videoModelReason(model: Model | undefined, hasFramePair: boolean) {
  if (!model) return "等待视频模型";
  if (isFirstLastFrameModel(model)) return "首帧与尾帧已自动匹配首尾帧工作流";
  if (hasFramePair && imageLimitFor(model) < 2) {
    return "当前模型不能同时使用首帧和尾帧";
  }
  if (imageLimitFor(model) > 0) {
    return "已按镜头参考素材匹配多参考生视频工作流";
  }
  return "已匹配文生视频工作流";
}

function renderCompatibilityError(model: Model, count: number) {
  const min = requiredImageMinimum(model);
  const max = imageLimitFor(model);
  return `当前工作流需要 ${min}–${max} 张参考图，镜头当前提供 ${count} 张。`;
}

function buildClipPrompt(
  shot: ClipShot,
  entities: DramaEntity[],
  hasFramePair: boolean,
) {
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
    direction.transition ? `转场：${direction.transition}。` : "",
    direction.referenceNotes
      ? `参考说明：${direction.referenceNotes}。`
      : "",
  ].filter(Boolean);
  const dramaticContext = contract
    ? [
        `场次价值变化：从“${contract.valueIn || "起始状态"}”转向“${
          contract.valueOut || "结束状态"
        }”。`,
        contract.characterObjectives.length
          ? `人物目标：${contract.characterObjectives.join("；")}。`
          : "",
        contract.obstacle ? `表演障碍：${contract.obstacle}。` : "",
        contract.tactics.length
          ? `行动战术：${contract.tactics.join("；")}。`
          : "",
        contract.turn ? `本镜头必须抵达的转折：${contract.turn}。` : "",
        contract.subtext ? `潜台词：${contract.subtext}。` : "",
        contract.performanceNotes
          ? `声台形表：${contract.performanceNotes}。`
          : "",
        contract.visualStrategy
          ? `视听策略：${contract.visualStrategy}。`
          : "",
        contract.soundNotes ? `声音设计：${contract.soundNotes}。` : "",
      ]
    : [];
  return [
    `电影镜头，${shot.title}。`,
    ...directionContext,
    ...dramaticContext,
    shot.description || "根据剧本描述完成克制、连贯的真实动作。",
    shot.dialogue ? `对白内容：${shot.dialogue}` : "",
    shot.grid9AssetId
      ? "九宫格连续帧是动作分解与顺序依据；保持每格之间的身份、服装、空间和光线连续。"
      : "",
    shot.storyboardAssetId
      ? "故事板是景别、机位和镜头运动依据；不要改变故事板确定的画面顺序和视觉焦点。"
      : "",
    hasFramePair
      ? "严格从首帧状态开始，在结束时自然抵达尾帧状态；人物身份、服装、场景、道具和光线全程一致。"
      : "保持引用素材中的角色身份、服装、场景、道具和光线一致。",
    entities.length
      ? `连续性对象：${entities
          .map(
            (entity) =>
              `${entity.name}（${entity.description || "遵循参考素材"}）`,
          )
          .join("；")}。`
      : "",
    `镜头时长约 ${shot.durationSeconds.toFixed(1)} 秒。动作自然克制，机位稳定；无跳切、无变脸、无额外人物。`,
  ]
    .filter(Boolean)
    .join("\n");
}
