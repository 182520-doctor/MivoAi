"use client";

import {
  CheckCircle2,
  Cpu,
  Search,
  Sparkles,
  Wifi,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { ModelsSectionNav } from "./ModelsSectionNav";

const capabilityLabels: Record<string, string> = {
  text: "文本对话",
  multimodal_understanding: "多模态理解",
  image_generation: "图片生成",
  image_processing: "图片处理",
  image_edit: "图片编辑",
  video_generation: "视频生成",
  video_from_image: "图生视频",
  video_processing: "视频处理",
  audio_processing: "音频处理",
  transcription: "语音转字幕",
};

const filters = [
  { id: "all", label: "全部模型" },
  { id: "text", label: "文本" },
  { id: "image", label: "图片" },
  { id: "video", label: "视频" },
  { id: "audio", label: "音频" },
] as const;

export function ModelControlCenter() {
  const settings = useModelSettings();
  const [filter, setFilter] = useState<(typeof filters)[number]["id"]>("all");
  const [search, setSearch] = useState("");

  const visibleModels = useMemo(
    () =>
      settings.models.filter((model) => {
        const query = search.trim().toLowerCase();
        if (
          query &&
          ![
            model.name,
            model.id,
            model.modelKey,
            model.providerName,
          ]
            .join(" ")
            .toLowerCase()
            .includes(query)
        ) {
          return false;
        }
        if (filter === "all") return true;
        if (filter === "image") {
          return model.capabilities.some((capability) =>
            capability.startsWith("image"),
          );
        }
        if (filter === "video") {
          return model.capabilities.some((capability) =>
            capability.startsWith("video"),
          );
        }
        if (filter === "audio") {
          return model.capabilities.some((capability) =>
            capability.startsWith("audio"),
          );
        }
        return model.capabilities.includes("text");
      }),
    [filter, search, settings.models],
  );

  const readyCount = settings.models.filter(
    (model) =>
      model.integrationStatus === "ready" &&
      (model.configured || model.providerId === "codex_local"),
  ).length;

  return (
    <main className="workbench-page model-page">
      <h1 className="visually-hidden">模型中心</h1>
      <ModelsSectionNav active="catalog" />

      <section className="model-summary-grid">
        <article>
          <Cpu size={20} />
          <div>
            <span>模型目录</span>
            <strong>{settings.models.length}</strong>
          </div>
        </article>
        <article>
          <CheckCircle2 size={20} />
          <div>
            <span>已就绪</span>
            <strong>{readyCount}</strong>
          </div>
        </article>
        <article>
          <Wifi size={20} />
          <div>
            <span>默认文本模型</span>
            <strong>{settings.selectedModel?.name ?? "未选择"}</strong>
          </div>
        </article>
      </section>

      <section className="model-catalog model-catalog-full">
        <div className="model-catalog-toolbar">
          <div className="model-filter-bar">
            {filters.map((item) => (
              <button
                key={item.id}
                className={filter === item.id ? "active" : ""}
                type="button"
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="model-catalog-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索模型名称、ID 或供应商"
            />
          </label>
        </div>

          <div className="model-card-grid">
            {visibleModels.map((model) => {
              const configured =
                model.configured || model.providerId === "codex_local";
              const defaultKind = model.capabilities.includes("text")
                ? "text"
                : model.capabilities.includes("image_generation")
                  ? "image"
                  : model.capabilities.includes("video_generation")
                    ? "video"
                    : null;
              const isDefault =
                defaultKind === "text"
                  ? settings.selectedModelId === model.id
                  : defaultKind === "image"
                    ? settings.preferences?.defaultImageModelId === model.id
                    : defaultKind === "video"
                      ? settings.preferences?.defaultVideoModelId === model.id
                      : false;
              return (
                <article
                  className={`model-card provider-${model.providerId}`}
                  key={model.id}
                >
                  <div className="model-card-head">
                    <span className="model-provider-icon">
                      <Cpu size={18} />
                    </span>
                    <div>
                      <span>{model.providerName}</span>
                      <h2>{model.name}</h2>
                    </div>
                    <span
                      className={`model-status ${
                        configured && model.integrationStatus === "ready"
                          ? "ready"
                          : ""
                      }`}
                    >
                      {model.integrationStatus === "ready"
                        ? configured
                          ? "已配置"
                          : "缺凭证"
                        : "待接入"}
                    </span>
                  </div>
                  <code>{model.id}</code>
                  {model.kind === "comfy_workflow" && (
                    <span className="workflow-model-source">
                      ComfyUI 工作流模型
                    </span>
                  )}
                  <div className="model-capabilities">
                    {model.capabilities.map((capability) => (
                      <span key={capability}>
                        {capabilityLabels[capability] ?? capability}
                      </span>
                    ))}
                  </div>
                  <div className="model-meta-row">
                    <span>执行方式</span>
                    <strong>
                      {model.executionMode === "async" ? "异步任务" : "同步"}
                    </strong>
                  </div>
                  <div className="model-card-actions">
                    <button
                      type="button"
                      disabled={!defaultKind || isDefault}
                      onClick={() => {
                        if (defaultKind === "text") {
                          void settings.selectModel(model.id);
                        } else if (defaultKind === "image") {
                          void settings.selectMediaModel(model.id, "image");
                        } else if (defaultKind === "video") {
                          void settings.selectMediaModel(model.id, "video");
                        }
                      }}
                    >
                      {isDefault
                        ? "当前默认"
                        : defaultKind === "image"
                          ? "设为默认图片"
                          : defaultKind === "video"
                            ? "设为默认视频"
                            : "设为默认文本"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>

          {visibleModels.length === 0 && (
            <div className="empty-library model-empty">
              <Sparkles size={25} />
              <h2>当前分类没有模型</h2>
            </div>
          )}
      </section>
    </main>
  );
}
