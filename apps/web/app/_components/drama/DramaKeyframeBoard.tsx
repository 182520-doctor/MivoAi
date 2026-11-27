"use client";

import {
  ArrowRight,
  CheckCircle2,
  CircleX,
  Clapperboard,
  Image as ImageIcon,
  Images,
  Layers3,
  LoaderCircle,
  Play,
  RefreshCw,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { updateDramaAssetCandidate } from "../../_features/drama/api";
import type { DramaAssetCandidate } from "../../_features/drama/types";
import { mediaAssetUrl } from "../../_features/media/api";
import { useDramaAssets } from "../../_features/drama/useDramaAssets";
import { useDramaKeyframes } from "../../_features/drama/useDramaKeyframes";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { DramaCandidateHistory } from "./DramaCandidateHistory";
import { DramaEpisodeAssetShelf } from "./DramaEpisodeAssetShelf";
import { DramaShotDirectionReview } from "./DramaShotDirectionReview";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";

type DramaKeyframeBoardProps = {
  projectId: string;
  episodeId?: string | null;
  initialShotId?: string | null;
  refreshToken?: number;
  onOpenAgent?: (context?: string) => void;
};

export function DramaKeyframeBoard({
  projectId,
  episodeId,
  initialShotId,
  refreshToken = 0,
  onOpenAgent,
}: DramaKeyframeBoardProps) {
  const models = useModelSettings();
  const library = useDramaAssets(projectId);
  const production = useDramaProduction(projectId);
  const shots = useMemo(
    () =>
      production.episodes
        .filter((episode) => !episodeId || episode.id === episodeId)
        .flatMap((episode) =>
        episode.scenes.flatMap((scene) =>
          scene.shots.map((shot) => ({
            ...shot,
            episodeTitle: episode.title,
            sceneHeading: scene.heading,
            sceneContract: episode.plan.sceneContracts.find(
              (contract) => contract.sceneNumber === scene.sceneNumber,
            ),
          })),
        ),
        ),
    [episodeId, production.episodes],
  );
  const generation = useDramaKeyframes({
    models: models.models,
    preferredModelId: models.preferences?.defaultImageModelId,
    shots,
    entities: library.entities,
    attachShotAssets: production.attachShotAssets,
    initialShotId,
  });
  const assetMap = useMemo(
    () => new Map(library.assets.map((asset) => [asset.id, asset])),
    [library.assets],
  );
  const episodeEntities = useMemo(() => {
    const entityIds = new Set(
      shots.flatMap(
        (shot) =>
          shot.entityReferences?.map((reference) => reference.entityId) ?? [],
      ),
    );
    return library.entities.filter((entity) => entityIds.has(entity.id));
  }, [library.entities, shots]);
  const resultIds = generation.task?.resultAssetIds ?? [];
  const progress = generation.task?.progress ?? 0;
  const [candidateBusyId, setCandidateBusyId] = useState<string | null>(
    null,
  );
  const readyCount = shots.filter(
    (shot) => shot.status !== "planned" || shot.firstFrameAssetId,
  ).length;
  const candidateSlot =
    generation.outputSlot === "first"
      ? "first_frame"
      : generation.outputSlot === "last"
        ? "last_frame"
        : generation.outputSlot;
  const persistedCandidates = (generation.activeShot?.candidates ?? []).filter(
    (candidate) => candidate.slot === candidateSlot,
  );
  const activeSlotAssetId =
    generation.outputSlot === "first"
      ? generation.activeShot?.firstFrameAssetId
      : generation.outputSlot === "last"
        ? generation.activeShot?.lastFrameAssetId
        : generation.outputSlot === "grid9"
          ? generation.activeShot?.grid9AssetId
          : generation.activeShot?.storyboardAssetId;

  async function selectPersistedCandidate(
    candidate: DramaAssetCandidate,
  ) {
    setCandidateBusyId(candidate.id);
    try {
      await generation.attachCandidate(
        candidate.assetId,
        generation.outputSlot,
      );
    } finally {
      setCandidateBusyId(null);
    }
  }

  async function rejectCandidate(candidate: DramaAssetCandidate) {
    setCandidateBusyId(candidate.id);
    try {
      await updateDramaAssetCandidate(candidate.id, "rejected");
      await production.refresh();
    } finally {
      setCandidateBusyId(null);
    }
  }

  function planEpisodeKeyframes() {
    if (!onOpenAgent) return;
    onOpenAgent(
      [
        "请为当前分集规划缺失的分镜画面。",
        "读取本集镜头、已关联角色/场景资产和现有首尾帧，",
        "选择合适图片工作流后调用 zaojing_plan_drama_production_run 创建待确认任务图。",
        "不要立即启动，先展示将生成的镜头槽位、参考资产和模型。",
      ].join("\n"),
    );
  }

  useEffect(() => {
    if (!refreshToken) return;
    void production.refresh();
    void library.refresh();
    void models.loadSettings();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  return (
    <section className="drama-keyframe-board">
      <header className="drama-keyframe-head">
        <div>
          <span className="eyebrow">Visual Continuity</span>
          <h3>分镜关键帧</h3>
          <p>从镜头和锁定资产自动组装参考图，选择合适工作流生成首帧。</p>
        </div>
        <div className="drama-keyframe-summary">
          <span><strong>{readyCount}</strong> / {shots.length} 镜就绪</span>
          <span>
            <Sparkles size={13} />
            {generation.selectedModel?.name ?? "等待图片模型"}
          </span>
          <button
            className="drama-episode-ai-generate"
            type="button"
            disabled={!onOpenAgent || !shots.length}
            onClick={planEpisodeKeyframes}
          >
            <WandSparkles size={15} />
            AI 编排本集分镜
          </button>
        </div>
      </header>

      {production.loading || library.loading ? (
        <div className="drama-stage-loading">
          正在读取本集镜头与资产生成契约…
        </div>
      ) : !shots.length ? (
        <div className="drama-keyframe-empty">
          <Clapperboard size={32} />
          <strong>还没有镜头</strong>
          <p>先完成剧本拆解，建立分集、场次和镜头，再生成关键帧。</p>
        </div>
      ) : (
        <div className="drama-keyframe-layout">
          <aside className="drama-keyframe-shots">
            <DramaEpisodeAssetShelf
              entities={episodeEntities}
              assets={assetMap}
              compact
            />
            <div className="drama-keyframe-panel-title">
              <span>镜头队列</span>
              <small>{shots.length} 个镜头</small>
            </div>
            <div className="drama-keyframe-shot-list">
              {shots.map((shot) => {
                const frame = shot.firstFrameAssetId
                  ? assetMap.get(shot.firstFrameAssetId)
                  : null;
                return (
                  <button
                    key={shot.id}
                    className={
                      shot.id === generation.activeShot?.id ? "active" : ""
                    }
                    type="button"
                    onClick={() => generation.setActiveShotId(shot.id)}
                  >
                    <span className="drama-keyframe-shot-thumb">
                      {frame ? (
                        <img src={backendResourceUrl(frame.url)} alt="" />
                      ) : (
                        <ImageIcon size={20} />
                      )}
                    </span>
                    <span>
                      <small>
                        {shot.episodeTitle} · 镜 {shot.shotNumber}
                      </small>
                      <strong>{shot.title}</strong>
                      <em>
                        {shot.firstFrameAssetId ? "关键帧已绑定" : "待生成"}
                      </em>
                    </span>
                    {shot.firstFrameAssetId ? (
                      <CheckCircle2 size={15} />
                    ) : (
                      <ArrowRight size={14} />
                    )}
                  </button>
                );
              })}
            </div>
          </aside>

          <section className="drama-keyframe-stage">
            {generation.activeShot && (
              <>
                <div className="drama-keyframe-stage-head">
                  <div>
                    <span>
                      {generation.activeShot.sceneHeading} · 镜头{" "}
                      {generation.activeShot.shotNumber}
                    </span>
                    <h4>{generation.activeShot.title}</h4>
                    <p>{generation.activeShot.description || "尚未填写画面描述"}</p>
                  </div>
                  <span className="drama-keyframe-duration">
                    {generation.activeShot.durationSeconds}s
                  </span>
                </div>

                <DramaShotDirectionReview
                  shot={generation.activeShot}
                  onOpenAgent={onOpenAgent}
                />

                <div className="drama-keyframe-context">
                  <div className="drama-keyframe-panel-title">
                    <span>自动参考素材</span>
                    <small>
                      {generation.referenceAssets.length} 张 · 工作流上限{" "}
                      {generation.imageLimit}
                    </small>
                  </div>
                  {generation.referenceAssets.length ? (
                    <div className="drama-keyframe-reference-row">
                      {generation.referenceAssets
                        .slice(0, 10)
                        .map((assetId, index) => {
                          const asset = assetMap.get(assetId);
                          return (
                            <div key={assetId}>
                              {asset ? (
                                <img src={backendResourceUrl(asset.url)} alt="" />
                              ) : (
                                <ImageIcon size={18} />
                              )}
                              <span>{index + 1}</span>
                            </div>
                          );
                        })}
                    </div>
                  ) : (
                    <div className="drama-keyframe-no-reference">
                      <Images size={20} />
                      <p>
                        该镜头还没有引用资产。可继续文生图，但建议先在资产阶段
                        关联角色和场景以保持一致性。
                      </p>
                    </div>
                  )}
                  <div className="drama-keyframe-entities">
                    {generation.referencedEntities.map((entity) => (
                      <span key={entity.id}>
                        {entity.name}
                        <small>{entity.kind}</small>
                      </span>
                    ))}
                  </div>
                </div>

                <div className="drama-keyframe-controls">
                  <label>
                    <span>生成目标</span>
                    <select
                      value={generation.outputSlot}
                      disabled={generation.submitting}
                      onChange={(event) =>
                        generation.setOutputSlot(
                          event.target.value as
                            | "first"
                            | "last"
                            | "grid9"
                            | "storyboard",
                        )
                      }
                    >
                      <option value="first">镜头首帧</option>
                      <option value="last">镜头尾帧</option>
                      <option value="grid9">九宫格连续帧</option>
                      <option value="storyboard">电影故事板</option>
                    </select>
                  </label>
                  <label>
                    <span>图片工作流</span>
                    <select
                      value={generation.selectedModelId}
                      disabled={generation.submitting}
                      onChange={(event) =>
                        generation.setSelectedModelId(event.target.value)
                      }
                    >
                      {generation.imageModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="drama-auto-model-note">
                    <WandSparkles size={14} />
                    <span>
                      {generation.referenceAssets.length
                        ? "已按参考图数量自动匹配参考生图工作流"
                        : "已匹配文生图工作流"}
                    </span>
                  </div>
                  <label className="drama-keyframe-prompt">
                    <span>关键帧提示词</span>
                    <textarea
                      value={generation.prompt}
                      onChange={(event) =>
                        generation.setPrompt(event.target.value)
                      }
                      rows={6}
                    />
                  </label>
                  <button
                    className="drama-prompt-save"
                    type="button"
                    disabled={!generation.prompt.trim()}
                    onClick={() => void generation.savePrompt()}
                  >
                    保存为当前提示词版本
                  </button>
                </div>

                {generation.error && (
                  <div className="drama-generation-error">
                    <CircleX size={16} />
                    <span>{generation.error}</span>
                  </div>
                )}

                {generation.submitting ? (
                  <button
                    className="drama-keyframe-generate busy"
                    type="button"
                    onClick={generation.cancel}
                  >
                    <LoaderCircle className="spin" size={17} />
                    ComfyUI 生成中 {progress ? `${progress}%` : ""}
                    <span>点击停止等待</span>
                  </button>
                ) : (
                  <button
                    className="drama-keyframe-generate"
                    type="button"
                    disabled={
                      !generation.selectedModel ||
                      !generation.prompt.trim() ||
                      generation.referenceAssets.length <
                        generation.minimumImages ||
                      generation.missingRequiredParameters.length > 0
                    }
                    onClick={() => void generation.generate()}
                  >
                    <Play size={16} />
                    {keyframeOutputLabel(generation.outputSlot)}
                    <span>{generation.selectedModel?.name ?? "请选择模型"}</span>
                  </button>
                )}
              </>
            )}
          </section>

          <aside className="drama-keyframe-results">
            <div className="drama-keyframe-panel-title">
              <span>任务与候选</span>
              <small>{resultIds.length} 个结果</small>
            </div>
            {generation.task ? (
              <>
                <div className="drama-keyframe-task">
                  <div>
                    {generation.task.status === "succeeded" ? (
                      <CheckCircle2 size={18} />
                    ) : generation.task.status === "failed" ? (
                      <CircleX size={18} />
                    ) : (
                      <LoaderCircle className="spin" size={18} />
                    )}
                    <span>
                      <strong>{taskStatusLabel(generation.task.status)}</strong>
                      <small>{generation.task.modelName || generation.task.modelId}</small>
                    </span>
                  </div>
                  <div className="drama-keyframe-progress">
                    <span style={{ width: `${progress || 4}%` }} />
                  </div>
                  <code>{generation.task.id.slice(0, 8)}</code>
                </div>
                {resultIds.length ? (
                  <div className="drama-keyframe-candidates">
                    {resultIds.map((assetId, index) => (
                      <article key={assetId}>
                        <img src={mediaAssetUrl(assetId)} alt={`候选 ${index + 1}`} />
                        <div>
                          <span>候选 {String(index + 1).padStart(2, "0")}</span>
                          <button
                            type="button"
                            onClick={() =>
                              void generation.attachCandidate(assetId, "first")
                            }
                          >
                            设为首帧
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void generation.attachCandidate(assetId, "last")
                            }
                          >
                            设为尾帧
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void generation.attachCandidate(
                                assetId,
                                "grid9",
                              )
                            }
                          >
                            设为九宫格
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void generation.attachCandidate(
                                assetId,
                                "storyboard",
                              )
                            }
                          >
                            设为故事板
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="drama-keyframe-task-note">
                    <Layers3 size={20} />
                    <p>任务完成后，所有候选会显示在这里。</p>
                  </div>
                )}
              </>
            ) : (
              <div className="drama-keyframe-results-empty">
                <Sparkles size={24} />
                <strong>等待生成</strong>
                <p>提交后会显示真实任务状态，并自动把首张结果绑定为镜头首帧。</p>
              </div>
            )}

            <DramaCandidateHistory
              title={`${keyframeSlotLabel(generation.outputSlot)}历史`}
              candidates={persistedCandidates}
              mediaType="image"
              busyCandidateId={candidateBusyId}
              onSelect={selectPersistedCandidate}
              onReject={rejectCandidate}
            />

            <div className="drama-keyframe-current">
              <span>当前{keyframeSlotLabel(generation.outputSlot)}</span>
              {activeSlotAssetId ? (
                <img
                  src={mediaAssetUrl(activeSlotAssetId)}
                  alt={`当前镜头${keyframeSlotLabel(generation.outputSlot)}`}
                />
              ) : (
                <div><ImageIcon size={24} /><small>尚未绑定</small></div>
              )}
            </div>
            <div className="drama-keyframe-slot-status">
              <span>
                尾帧
                <strong>
                  {generation.activeShot?.lastFrameAssetId
                    ? "已绑定"
                    : "未绑定"}
                </strong>
              </span>
              <span>
                九宫格
                <strong>
                  {generation.activeShot?.grid9AssetId
                    ? "已绑定"
                    : "未绑定"}
                </strong>
              </span>
              <span>
                故事板
                <strong>
                  {generation.activeShot?.storyboardAssetId
                    ? "已绑定"
                    : "未绑定"}
                </strong>
              </span>
            </div>
            <button
              className="drama-keyframe-refresh"
              type="button"
              onClick={() => {
                void production.refresh();
                void library.refresh();
                void models.loadSettings();
              }}
            >
              <RefreshCw size={14} /> 刷新模型与任务状态
            </button>
          </aside>
        </div>
      )}
    </section>
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

function keyframeOutputLabel(
  slot: "first" | "last" | "grid9" | "storyboard",
) {
  return {
    first: "生成镜头首帧",
    last: "生成镜头尾帧",
    grid9: "生成九宫格连续帧",
    storyboard: "生成电影故事板",
  }[slot];
}

function keyframeSlotLabel(
  slot: "first" | "last" | "grid9" | "storyboard",
) {
  return {
    first: "首帧",
    last: "尾帧",
    grid9: "九宫格",
    storyboard: "故事板",
  }[slot];
}
