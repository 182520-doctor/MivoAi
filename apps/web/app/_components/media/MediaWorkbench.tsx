"use client";

import {
  CheckCircle2,
  CircleX,
  FileText,
  Image as ImageIcon,
  Layers3,
  ListTodo,
  LoaderCircle,
  Music2,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Video,
} from "lucide-react";
import NextImage from "next/image";
import { mediaAssetUrl } from "../../_features/media/api";
import { useMediaGeneration } from "../../_features/media/useMediaGeneration";
import { useModelSettings } from "../../_features/models/useModelSettings";
import type { WorkflowParameter } from "../../_features/workflows/types";

const capabilities = [
  { id: "image", label: "图片", icon: ImageIcon },
  { id: "video", label: "视频", icon: Video },
  { id: "audio", label: "音频", icon: Music2 },
] as const;

export function MediaWorkbench() {
  const modelSettings = useModelSettings();
  const generation = useMediaGeneration(
    modelSettings.models,
    modelSettings.preferences,
  );
  const assetIds = generation.task?.resultAssetIds ?? [];
  const capabilityLabel =
    capabilities.find((item) => item.id === generation.mode)?.label ?? "图片";
  const isWorkflowModel = generation.model?.kind === "comfy_workflow";
  const missingRequired = generation.formParameters.some((parameter) => {
    if (parameter.type === "assets") return false;
    if (!parameter.required) return false;
    const modelValue = generation.parameterValues[parameter.key];
    return modelValue == null || modelValue === "";
  }) ||
    generation.referenceInputs.some(
      (parameter) =>
        parameter.required &&
        (generation.assetIdsByParameter[parameter.type]?.length ?? 0) <
          (parameter.min ?? 0),
    );

  return (
    <main className="workbench-page">
      <h1 className="visually-hidden">多模态创作工作台</h1>
      <section className="media-layout">
        <aside className="workbench-panel media-controls">
          <div className="panel-heading">
            <div>
              <SlidersHorizontal size={17} />
              <strong>生成设置</strong>
            </div>
            <span className="mini-badge">ComfyUI</span>
          </div>

          <div className="capability-switch" role="tablist" aria-label="生成类型">
            {capabilities.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={generation.mode === id ? "active" : ""}
                type="button"
                role="tab"
                aria-selected={generation.mode === id}
                onClick={() => generation.setMode(id)}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>

          <label className="workbench-field">
            <span>生成 / 处理模型</span>
            <select
              value={generation.selectedModelId}
              onChange={(event) =>
                generation.setSelectedModelId(event.target.value)
              }
            >
              {generation.availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                  {model.kind === "comfy_workflow"
                    ? generation.mode === "image"
                      ? "（图片工作流）"
                      : generation.mode === "video"
                        ? "（视频工作流）"
                        : "（音频工作流）"
                    : "（内置）"}
                </option>
              ))}
            </select>
          </label>

          <label className="workbench-field">
            <span>
              提示词{generation.promptRequired ? "" : "（可选）"}
            </span>
            <textarea
              aria-label="生成提示词"
              value={generation.prompt}
              onChange={(event) => generation.setPrompt(event.target.value)}
              placeholder={
                generation.mode === "audio" && !generation.promptRequired
                  ? "此音频处理工作流无需额外提示词"
                  : generation.promptRequired
                  ? "描述画面主体、风格、构图、光线和运镜…"
                  : "此工作流可以只使用参考素材、参数或工作流内置提示词"
              }
              rows={6}
            />
          </label>

          {isWorkflowModel ? (
            <div className="workflow-parameter-grid">
              {generation.formParameters
                .filter((parameter) => parameter.type !== "assets")
                .map((parameter) => (
                  <WorkflowParameterInput
                    key={parameter.key}
                    parameter={parameter}
                    value={generation.parameterValues[parameter.key]}
                    onChange={(value) =>
                      generation.setParameter(parameter.key, value)
                    }
                  />
                ))}
            </div>
          ) : generation.mode === "audio" ? null : (
            <div className="field-pair">
              <label className="workbench-field">
                <span>画幅</span>
                <select
                  value={generation.aspectRatio}
                  onChange={(event) =>
                    generation.setAspectRatio(event.target.value)
                  }
                >
                  <option value="16:9">16:9 横屏</option>
                  <option value="9:16">9:16 竖屏</option>
                  <option value="1:1">1:1 方形</option>
                </select>
              </label>
              <label className="workbench-field">
                <span>{generation.mode === "image" ? "数量" : "视频长度"}</span>
                <select
                  value={generation.count}
                  disabled={generation.mode === "video"}
                  onChange={(event) =>
                    generation.setCount(Number(event.target.value))
                  }
                >
                  {generation.mode === "image" ? (
                    <>
                      <option value="1">1 张</option>
                      <option value="2">2 张</option>
                      <option value="4">4 张</option>
                    </>
                  ) : (
                    <option value="1">17 帧 / 约 1.4 秒</option>
                  )}
                </select>
              </label>
            </div>
          )}

          {generation.referenceInputs.map((parameter) => {
            const selected =
              generation.assetIdsByParameter[parameter.type] ?? [];
            const Icon =
              parameter.type === "video"
                ? Video
                : parameter.type === "audio"
                  ? Music2
                  : parameter.type === "file"
                    ? FileText
                    : ImageIcon;
            return (
              <div className="dynamic-assets" key={parameter.type}>
                <label className="asset-upload-button">
                  <Icon size={18} />
                  <div>
                    <strong>
                      {parameter.label}
                      {generation.uploadingAssets ? "（上传中）" : ""}
                    </strong>
                    <span>
                      已选 {selected.length} 个
                      {parameter.min != null
                        ? ` · 至少 ${parameter.min}`
                        : ""}
                      {parameter.max != null
                        ? ` · 最多 ${parameter.max}`
                        : ""}
                    </span>
                  </div>
                  <input
                    type="file"
                    accept={acceptForAssetType(parameter.type)}
                    multiple
                    disabled={generation.uploadingAssets}
                    onChange={(event) => {
                      const files = Array.from(event.target.files ?? []);
                      void generation.uploadAssets(parameter.type, files);
                      event.target.value = "";
                    }}
                  />
                </label>
                {selected.length > 0 && (
                  <div className="asset-thumbnails">
                    {selected.map((assetId, index) => (
                      <button
                        key={assetId}
                        type="button"
                        title="移除素材"
                        onClick={() =>
                          generation.removeAsset(parameter.type, assetId)
                        }
                      >
                        {parameter.type === "video" ? (
                          <video
                            src={mediaAssetUrl(assetId)}
                            muted
                            preload="metadata"
                          />
                        ) : parameter.type === "audio" ? (
                          <Music2 size={24} />
                        ) : parameter.type === "file" ? (
                          <FileText size={24} />
                        ) : (
                          <img
                            src={mediaAssetUrl(assetId)}
                            alt={`${parameter.label} ${index + 1}`}
                          />
                        )}
                        <span>{index + 1}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {!isWorkflowModel && (
            <div className="reference-box">
              <Upload size={19} />
              <div>
                <strong>参考素材</strong>
                <span>内置模型当前仅支持文本输入</span>
              </div>
            </div>
          )}

          <div className="provider-row">
            <span>执行模型</span>
            <strong>{generation.model?.name ?? "等待模型目录"}</strong>
          </div>

          {generation.isSubmitting ? (
            <button
              className="primary-action stop-generation"
              type="button"
              onClick={generation.cancel}
            >
              停止等待
            </button>
          ) : (
            <button
              className="primary-action"
              type="button"
              disabled={
                (generation.promptRequired && !generation.prompt.trim()) ||
                !generation.model ||
                missingRequired ||
                generation.uploadingAssets
              }
              onClick={() => void generation.generate()}
            >
              {generation.mode === "audio"
                ? "处理音频"
                : `生成${capabilityLabel}`}
              <span>本机 ComfyUI</span>
            </button>
          )}
        </aside>

        <section className="workbench-panel media-canvas">
          <div className="panel-heading">
            <div>
              <Layers3 size={17} />
              <strong>结果画布</strong>
            </div>
            <span className="panel-caption">
              {assetIds.length
                ? `${assetIds.length} 个结果`
                : generation.task
                  ? "生成中"
                  : "等待生成"}
            </span>
          </div>

          <div className="canvas-stage">
            {assetIds.length ? (
              generation.mode === "video" ? (
                <div className="canvas-video-frame">
                  <video
                    className="canvas-result canvas-video-result"
                    src={mediaAssetUrl(assetIds[0])}
                    controls
                    autoPlay
                    loop
                  />
                </div>
              ) : generation.mode === "audio" ? (
                <div className="canvas-audio-grid">
                  {assetIds.map((assetId, index) => (
                    <article key={assetId}>
                      <span>
                        <Music2 size={17} />
                        {audioTrackLabel(
                          generation.task,
                          assetId,
                          index,
                        )}
                      </span>
                      <audio
                        src={mediaAssetUrl(assetId)}
                        controls
                        preload="metadata"
                      />
                      <code>{assetId.slice(0, 8)}</code>
                    </article>
                  ))}
                </div>
              ) : (
                <div
                  className={`canvas-result-grid count-${Math.min(
                    assetIds.length,
                    4,
                  )}`}
                >
                  {assetIds.map((assetId) => (
                    <img
                      key={assetId}
                      className="canvas-result"
                      src={mediaAssetUrl(assetId)}
                      alt="ComfyUI 生成结果"
                    />
                  ))}
                </div>
              )
            ) : (
              <>
                <NextImage
                  className="canvas-sample"
                  src="/demo-city.png"
                  alt="多模态创作结果画布示例"
                  width={1200}
                  height={760}
                  priority
                />
                <span className="canvas-label">
                  示例素材，提交任务后将在这里显示真实结果
                </span>
              </>
            )}
          </div>

          {generation.error && (
            <div className="generation-error">
              <CircleX size={16} />
              <span>{generation.error}</span>
            </div>
          )}

          <div className="canvas-footer">
            <span>
              生成结果已保存到素材库，刷新页面后仍可访问。
            </span>
            <div>
              <button type="button" disabled={!assetIds.length}>
                保留
              </button>
              <button type="button" disabled={!assetIds.length}>
                继续编辑
              </button>
            </div>
          </div>
        </section>

        <aside className="workbench-panel task-rail">
          <div className="panel-heading">
            <div>
              <ListTodo size={17} />
              <strong>任务队列</strong>
            </div>
            <span className="queue-count">{generation.task ? 1 : 0}</span>
          </div>

          {generation.task ? (
            <div className="current-task">
              <div className="current-task-head">
                {generation.task.status === "succeeded" ? (
                  <CheckCircle2 size={18} />
                ) : generation.task.status === "failed" ? (
                  <CircleX size={18} />
                ) : (
                  <LoaderCircle className="spin" size={18} />
                )}
                <div>
                  <strong>{taskStatusLabel(generation.task.status)}</strong>
                  <span>
                    {taskTypeLabel(generation.task.taskType)}
                    任务
                  </span>
                </div>
              </div>
              <div className="task-progress-track">
                <span
                  style={{
                    width: `${generation.task.progress ?? 8}%`,
                  }}
                />
              </div>
              <code>{generation.task.id}</code>
              {generation.task.providerTaskId && (
                <p>ComfyUI：{generation.task.providerTaskId}</p>
              )}
              {generation.task.errorMessage && (
                <p className="task-error">{generation.task.errorMessage}</p>
              )}
            </div>
          ) : (
            <div className="task-empty">
              <span>
                <Sparkles size={20} />
              </span>
              <strong>还没有生成任务</strong>
              <p>填写提示词并提交后，排队、进度和结果会显示在这里。</p>
            </div>
          )}

          <div className="task-rail-note">
            <span className="connection-dot online" />
            <p>
              当前模型来自工作流中心，参考图数量和参数由所选工作流自动决定。
              生成耗时取决于显卡与队列。
            </p>
          </div>
        </aside>
      </section>
    </main>
  );
}

type WorkflowParameterInputProps = {
  parameter: WorkflowParameter;
  value: unknown;
  onChange: (value: unknown) => void;
};

function WorkflowParameterInput({
  parameter,
  value,
  onChange,
}: WorkflowParameterInputProps) {
  const options = parameter.options?.map(String);
  if (parameter.type === "boolean") {
    return (
      <label className="workbench-field parameter-checkbox">
        <span>{parameter.label}</span>
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
      </label>
    );
  }
  if (options?.length) {
    return (
      <label className="workbench-field">
        <span>{parameter.label}</span>
        <select
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="workbench-field">
      <span>{parameter.label}</span>
      <input
        type={parameter.type === "integer" || parameter.type === "number" ? "number" : "text"}
        value={String(value ?? "")}
        min={parameter.min}
        max={parameter.max}
        onChange={(event) =>
          onChange(
            parameter.type === "integer" || parameter.type === "number"
              ? Number(event.target.value)
              : event.target.value,
          )
        }
      />
    </label>
  );
}

function taskStatusLabel(status: string) {
  return {
    pending: "等待提交",
    queued: "排队中",
    running: "ComfyUI 生成中",
    succeeded: "生成完成",
    failed: "生成失败",
    canceled: "已取消",
  }[status] ?? status;
}

function taskTypeLabel(taskType: string) {
  return {
    image_generation: "图片",
    image_processing: "图片处理",
    video_generation: "视频",
    video_processing: "视频处理",
    audio_processing: "音频处理",
    transcription: "语音转字幕",
  }[taskType] ?? taskType;
}

function audioTrackLabel(
  task: ReturnType<typeof useMediaGeneration>["task"],
  assetId: string,
  index: number,
) {
  const asset = task?.resultAssets?.find((item) => item.id === assetId);
  const filename = String(asset?.metadata.originalFilename ?? "").toLowerCase();
  const labels: Array<[string, string]> = [
    ["vocals", "人声 / Vocals"],
    ["drums", "鼓 / Drums"],
    ["bass", "贝斯 / Bass"],
    ["other", "其他 / Other"],
  ];
  return labels.find(([stem]) => filename.includes(stem))?.[1] ??
    `音频轨道 ${index + 1}`;
}

function acceptForAssetType(assetType?: string) {
  if (assetType === "video") return "video/*,.mkv,.mov";
  if (assetType === "audio") return "audio/*,.m4a,.flac,.ogg";
  if (assetType === "file") return ".txt,.json,.csv,.pdf,.srt,.ass";
  return "image/*";
}
