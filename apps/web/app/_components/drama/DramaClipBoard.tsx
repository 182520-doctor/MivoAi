"use client";

import {
  AudioLines,
  ArrowRight,
  CheckCircle2,
  CircleX,
  Clapperboard,
  Clock3,
  Film,
  FileText,
  Image as ImageIcon,
  Images,
  LayoutGrid,
  Layers3,
  ListVideo,
  LoaderCircle,
  Mic2,
  Music2,
  Play,
  RefreshCw,
  RotateCcw,
  Scissors,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createMediaTask,
  mediaAssetUrl,
  pollMediaTask,
} from "../../_features/media/api";
import { updateDramaAssetCandidate } from "../../_features/drama/api";
import type {
  DramaAssetCandidate,
} from "../../_features/drama/types";
import {
  loadSpeechVoices,
  normalizeAudio,
  synthesizeSpeech,
  transcribeAudio,
  upscaleVideo,
} from "../../_features/media/processingApi";
import { useDramaAssets } from "../../_features/drama/useDramaAssets";
import { useDramaClips } from "../../_features/drama/useDramaClips";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { DramaCandidateHistory } from "./DramaCandidateHistory";
import { DramaEpisodeAssetShelf } from "./DramaEpisodeAssetShelf";
import { DramaShotDirectionReview } from "./DramaShotDirectionReview";

type DramaClipBoardProps = {
  projectId: string;
  aspectRatio: string;
  episodeId?: string | null;
  initialShotId?: string | null;
  refreshToken?: number;
  onOpenAgent?: (context?: string) => void;
};

export function DramaClipBoard({
  projectId,
  aspectRatio,
  episodeId,
  initialShotId,
  refreshToken = 0,
  onOpenAgent,
}: DramaClipBoardProps) {
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
  const [viewMode, setViewMode] = useState<"board" | "editor">(
    initialShotId ? "editor" : "board",
  );
  const generation = useDramaClips({
    models: models.models,
    preferredModelId: models.preferences?.defaultVideoModelId,
    shots,
    entities: library.entities,
    aspectRatio,
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
  const extractProgress = generation.extractTask?.progress ?? 0;
  const readyCount = shots.filter((shot) => shot.videoAssetId).length;
  const [candidateBusyId, setCandidateBusyId] = useState<string | null>(
    null,
  );
  const persistedVideoCandidates = (
    generation.activeShot?.candidates ?? []
  ).filter((candidate) => candidate.slot === "video");
  const activeVideoUrl = generation.activeShot?.videoAssetId
    ? backendResourceUrl(
        assetMap.get(generation.activeShot.videoAssetId)?.url ??
          mediaAssetUrl(generation.activeShot.videoAssetId),
      )
    : null;
  const [voices, setVoices] = useState<
    Array<{ name: string; culture: string; gender?: string }>
  >([]);
  const [voiceName, setVoiceName] = useState(
    "Microsoft Huihui Desktop",
  );
  const [ttsText, setTtsText] = useState("");
  const [ttsRate, setTtsRate] = useState(0);
  const [ttsGenerating, setTtsGenerating] = useState(false);
  const [ttsError, setTtsError] = useState("");
  const [normalizingAudio, setNormalizingAudio] = useState(false);
  const [normalizeAudioError, setNormalizeAudioError] = useState("");
  const [separatingAudio, setSeparatingAudio] = useState(false);
  const [separationAudioError, setSeparationAudioError] = useState("");
  const [transcribingAudio, setTranscribingAudio] = useState(false);
  const [transcriptionAudioError, setTranscriptionAudioError] =
    useState("");
  const [interpolating, setInterpolating] = useState(false);
  const [interpolationError, setInterpolationError] = useState("");
  const [upscalingVideo, setUpscalingVideo] = useState(false);
  const [upscaleVideoError, setUpscaleVideoError] = useState("");

  async function selectPersistedVideoCandidate(
    candidate: DramaAssetCandidate,
  ) {
    setCandidateBusyId(candidate.id);
    try {
      await generation.attachVideo(candidate.assetId);
    } finally {
      setCandidateBusyId(null);
    }
  }

  async function rejectVideoCandidate(candidate: DramaAssetCandidate) {
    setCandidateBusyId(candidate.id);
    try {
      await updateDramaAssetCandidate(candidate.id, "rejected");
      await production.refresh();
    } finally {
      setCandidateBusyId(null);
    }
  }

  useEffect(() => {
    void loadSpeechVoices()
      .then((result) => {
        setVoices(result.voices);
        const chinese = result.voices.find((voice) =>
          voice.culture.toLowerCase().startsWith("zh"),
        );
        if (chinese) {
          setVoiceName((current) => current || chinese.name);
        }
      })
      .catch((error) => setTtsError((error as Error).message));
  }, []);

  useEffect(() => {
    if (!refreshToken) return;
    void production.refresh();
    void library.refresh();
    void models.loadSettings();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  useEffect(() => {
    const dialogue = generation.activeShot?.dialogue ?? "";
    setTtsText(dialogue);
    const speaker = dialogue.split(/[：:]/, 1)[0]?.trim() ?? "";
    const character = generation.referencedEntities.find(
      (entity) =>
        entity.kind === "character" &&
        speaker.includes(entity.name),
    );
    if (character?.voiceName) {
      setVoiceName(character.voiceName);
      setTtsRate(character.voiceRate ?? 0);
    }
    setTtsError("");
  }, [generation.activeShot?.id]);

  async function generateTts() {
    if (!generation.activeShot || !ttsText.trim() || ttsGenerating) return;
    setTtsGenerating(true);
    setTtsError("");
    try {
      const result = await synthesizeSpeech(
        ttsText.trim(),
        voiceName,
        ttsRate,
      );
      await production.attachShotAssets(generation.activeShot.id, {
        audioAssetId: result.assetId,
      });
    } catch (error) {
      setTtsError((error as Error).message);
    } finally {
      setTtsGenerating(false);
    }
  }

  async function interpolateVideo() {
    const shot = generation.activeShot;
    if (!shot?.videoAssetId || interpolating) return;
    const model = models.models.find(
      (item) =>
        item.capabilities.includes("video_generation") &&
        item.name.includes("视频补帧") &&
        item.integrationStatus === "ready",
    );
    if (!model) {
      setInterpolationError("模型中心还没有启用的视频补帧工作流");
      return;
    }
    setInterpolating(true);
    setInterpolationError("");
    try {
      const parameters = Object.fromEntries(
        (model.parameters ?? [])
          .filter(
            (parameter) =>
              parameter.type !== "assets" &&
              !parameter.derived &&
              parameter.default !== undefined,
          )
          .map((parameter) => [parameter.key, parameter.default]),
      );
      const created = await createMediaTask({
        providerId: model.providerId,
        modelId: model.id,
        taskType: "video_generation",
        prompt: "RIFE frame interpolation to 60fps",
        inputAssetIds: [],
        images: [],
        videos: [shot.videoAssetId],
        audios: [],
        files: [],
        parameters,
        clientRequestId: crypto.randomUUID(),
      });
      const controller = new AbortController();
      const completed = await pollMediaTask(
        created.id,
        () => undefined,
        controller.signal,
      );
      if (completed.status === "failed") {
        setInterpolationError(
          completed.errorMessage || "视频补帧失败",
        );
        return;
      }
      const assetId = completed.resultAssetIds[0];
      if (assetId) {
        await production.attachShotAssets(shot.id, {
          videoAssetId: assetId,
          status: "clip_ready",
        });
      }
    } catch (error) {
      setInterpolationError((error as Error).message);
    } finally {
      setInterpolating(false);
    }
  }

  async function upscaleShotVideo() {
    const shot = generation.activeShot;
    if (!shot?.videoAssetId || upscalingVideo) return;
    setUpscalingVideo(true);
    setUpscaleVideoError("");
    try {
      const result = await upscaleVideo(shot.videoAssetId, aspectRatio);
      await production.attachShotAssets(shot.id, {
        videoAssetId: result.assetId,
        status: "clip_ready",
      });
    } catch (error) {
      setUpscaleVideoError((error as Error).message);
    } finally {
      setUpscalingVideo(false);
    }
  }

  async function normalizeShotAudio() {
    const shot = generation.activeShot;
    if (!shot?.audioAssetId || normalizingAudio) return;
    setNormalizingAudio(true);
    setNormalizeAudioError("");
    try {
      const result = await normalizeAudio(shot.audioAssetId, -16);
      await production.attachShotAssets(shot.id, {
        audioAssetId: result.assetId,
      });
    } catch (error) {
      setNormalizeAudioError(
        error instanceof Error ? error.message : "音频响度标准化失败",
      );
    } finally {
      setNormalizingAudio(false);
    }
  }

  async function separateShotAudio() {
    const shot = generation.activeShot;
    if (!shot?.audioAssetId || separatingAudio) return;
    const model = models.models.find(
      (item) =>
        item.capabilities.includes("audio_processing") &&
        item.name.includes("音频四轨分离") &&
        item.integrationStatus === "ready",
    );
    if (!model) {
      setSeparationAudioError("模型中心还没有启用的音频四轨分离工作流");
      return;
    }
    setSeparatingAudio(true);
    setSeparationAudioError("");
    try {
      const created = await createMediaTask({
        providerId: model.providerId,
        modelId: model.id,
        taskType: "audio_processing",
        prompt: "",
        inputAssetIds: [],
        images: [],
        videos: [],
        audios: [shot.audioAssetId],
        files: [],
        parameters: {},
        clientRequestId: crypto.randomUUID(),
      });
      const controller = new AbortController();
      const completed = await pollMediaTask(
        created.id,
        () => undefined,
        controller.signal,
      );
      if (completed.status === "failed") {
        setSeparationAudioError(
          completed.errorMessage || "音频四轨分离失败",
        );
        return;
      }
      const vocals =
        completed.resultAssets?.find((asset) =>
          String(asset.metadata.originalFilename ?? "")
            .toLowerCase()
            .includes("vocals"),
        )?.id;
      if (!vocals) {
        setSeparationAudioError("分离完成，但没有找到人声轨道");
        return;
      }
      await production.attachShotAssets(shot.id, {
        audioAssetId: vocals,
      });
    } catch (error) {
      setSeparationAudioError(
        error instanceof Error ? error.message : "音频四轨分离失败",
      );
    } finally {
      setSeparatingAudio(false);
    }
  }

  async function transcribeShotAudio() {
    const shot = generation.activeShot;
    if (!shot?.audioAssetId || transcribingAudio) return;
    const episode = production.episodes.find((item) =>
      item.scenes.some((scene) =>
        scene.shots.some((sceneShot) => sceneShot.id === shot.id),
      ),
    );
    if (!episode) {
      setTranscriptionAudioError("没有找到当前镜头所属分集");
      return;
    }
    setTranscribingAudio(true);
    setTranscriptionAudioError("");
    try {
      const result = await transcribeAudio(shot.audioAssetId, "zh");
      const orderedShots = episode.scenes.flatMap((scene) => scene.shots);
      const shotIndex = orderedShots.findIndex((item) => item.id === shot.id);
      const offset = orderedShots
        .slice(0, Math.max(0, shotIndex))
        .reduce((total, item) => total + item.durationSeconds, 0);
      const generated = result.cues.map((cue) => ({
        startSeconds: Number((cue.startSeconds + offset).toFixed(3)),
        endSeconds: Number((cue.endSeconds + offset).toFixed(3)),
        text: cue.text,
      }));
      const merged = [...episode.subtitleCues, ...generated]
        .filter(
          (cue, index, cues) =>
            cues.findIndex(
              (item) =>
                item.startSeconds === cue.startSeconds &&
                item.endSeconds === cue.endSeconds &&
                item.text === cue.text,
            ) === index,
        )
        .sort((left, right) => left.startSeconds - right.startSeconds);
      await production.updateSubtitles(episode.id, merged);
    } catch (error) {
      setTranscriptionAudioError(
        error instanceof Error ? error.message : "语音转字幕失败",
      );
    } finally {
      setTranscribingAudio(false);
    }
  }

  function planEpisodeBatch() {
    if (!onOpenAgent) return;
    onOpenAgent(
      [
        "请把当前分镜阶段整理成本集可执行的视频任务图。",
        "先读取当前分集镜头、已绑定首尾帧、九宫格、故事板和角色/场景资产。",
        "只为本集缺失视频的镜头选择合适工作流，并调用 zaojing_plan_drama_production_run 创建待确认运行。",
        "不要立即启动；先展示镜头数量、模型、参考素材和预计任务数，等待我确认。",
      ].join("\n"),
    );
  }

  return (
    <section className="drama-keyframe-board drama-clip-board">
      <header className="drama-keyframe-head">
        <div>
          <span className="eyebrow">Shot Production</span>
          <h3>镜头视频与声音</h3>
          <p>自动选择文生视频、参考生视频或首尾帧工作流，并把成片回写镜头。</p>
        </div>
        <div className="drama-keyframe-summary">
          <span><strong>{readyCount}</strong> / {shots.length} 镜有视频</span>
          <span>
            <Film size={13} />
            {generation.selectedModel?.name ?? "等待视频模型"}
          </span>
          <div className="drama-shot-view-switch">
            <button
              className={viewMode === "board" ? "active" : ""}
              type="button"
              onClick={() => setViewMode("board")}
            >
              <LayoutGrid size={14} />
              分镜板
            </button>
            <button
              className={viewMode === "editor" ? "active" : ""}
              type="button"
              onClick={() => setViewMode("editor")}
            >
              <ListVideo size={14} />
              精细编辑
            </button>
          </div>
          <button
            className="drama-episode-ai-generate"
            type="button"
            disabled={!onOpenAgent || !shots.length}
            onClick={planEpisodeBatch}
          >
            <WandSparkles size={15} />
            AI 生成本集缺失镜头
          </button>
        </div>
      </header>

      {!shots.length ? (
        <div className="drama-keyframe-empty">
          <Clapperboard size={32} />
          <strong>还没有可制作的镜头</strong>
          <p>先完成剧本拆解和关键帧，再把镜头推进到视频阶段。</p>
        </div>
      ) : viewMode === "board" ? (
        <div className="drama-clip-storyboard">
          <DramaEpisodeAssetShelf
            entities={episodeEntities}
            assets={assetMap}
          />
          <section className="drama-clip-storyboard-head">
            <div>
              <span>本集分镜</span>
              <strong>{shots.length} 个片段</strong>
            </div>
            <p>
              先浏览整集画面与提示词，再选择片段进入精细生成和资产调整。
            </p>
          </section>
          <div className="drama-clip-storyboard-grid">
            {shots.map((shot, index) => {
              const entities = (shot.entityReferences ?? [])
                .flatMap((reference) => {
                  const entity = library.entities.find(
                    (item) => item.id === reference.entityId,
                  );
                  return entity ? [entity] : [];
                });
              return (
                <article
                  key={shot.id}
                  className={`${shot.videoAssetId ? "ready" : "missing"} ${
                    shot.status === "approved" ? "approved" : ""
                  }`}
                >
                  <button
                    className="drama-storyboard-thumb"
                    type="button"
                    onClick={() => {
                      generation.setActiveShotId(shot.id);
                      setViewMode("editor");
                    }}
                  >
                    {shot.videoAssetId ? (
                      <video
                        src={mediaAssetUrl(shot.videoAssetId)}
                        muted
                        preload="metadata"
                      />
                    ) : shot.firstFrameAssetId ? (
                      <img
                        src={mediaAssetUrl(shot.firstFrameAssetId)}
                        alt={shot.title}
                      />
                    ) : (
                      <span>
                        <Film size={28} />
                        等待画面
                      </span>
                    )}
                    <em>
                      片段 {String(index + 1).padStart(2, "0")}
                    </em>
                    <small>{shot.durationSeconds}s</small>
                  </button>
                  <div className="drama-storyboard-copy">
                    <header>
                      <strong>{shot.title}</strong>
                      <span>
                        {shot.status === "approved"
                          ? "导演已通过"
                          : shot.videoAssetId
                            ? "视频待审核"
                            : "待生成"}
                      </span>
                    </header>
                    <small>
                      {shot.episodeTitle} · {shot.sceneHeading}
                    </small>
                    <p>
                      {shot.description ||
                        shot.dialogue ||
                        "尚未填写镜头提示词"}
                    </p>
                    <div className="drama-storyboard-assets">
                      {entities.map((entity) => {
                        const assetId =
                          entity.primaryAssetId ??
                          Object.values(entity.assetSlots)[0];
                        const asset = assetId
                          ? assetMap.get(assetId)
                          : null;
                        return (
                          <span key={entity.id} title={entity.name}>
                            {asset ? (
                              <img src={backendResourceUrl(asset.url)} alt="" />
                            ) : (
                              <Images size={13} />
                            )}
                            {entity.name}
                          </span>
                        );
                      })}
                    </div>
                    {shot.statusHistory?.length ? (
                      <div className="drama-storyboard-review">
                        <Clock3 size={12} />
                        <span>
                          {reviewerLabel(shot.statusHistory[0].reviewer)}
                          {" · "}
                          {shotStatusLabel(
                            shot.statusHistory[0].toStatus,
                          )}
                          {" · "}
                          {formatReviewTime(
                            shot.statusHistory[0].createdAt,
                          )}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  <footer>
                    <button
                      type="button"
                      onClick={() => {
                        generation.setActiveShotId(shot.id);
                        setViewMode("editor");
                      }}
                    >
                      {shot.videoAssetId ? "查看与重做" : "进入生成"}
                    </button>
                    <button
                      className="primary"
                      type="button"
                      onClick={() => {
                        generation.setActiveShotId(shot.id);
                        setViewMode("editor");
                      }}
                    >
                      <WandSparkles size={13} />
                      AI 生成此镜
                    </button>
                    {shot.videoAssetId && (
                      <button
                        className={
                          shot.status === "approved" ? "" : "approve"
                        }
                        type="button"
                        onClick={() =>
                          void production.setShotStatus(
                            shot.id,
                            shot.status === "approved"
                              ? "clip_ready"
                              : "approved",
                          )
                        }
                      >
                        {shot.status === "approved" ? (
                          <RotateCcw size={13} />
                        ) : (
                          <CheckCircle2 size={13} />
                        )}
                        {shot.status === "approved"
                          ? "退回复做"
                          : "通过此镜"}
                      </button>
                    )}
                  </footer>
                </article>
              );
            })}
          </div>
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
              {shots.map((shot) => (
                <button
                  key={shot.id}
                  className={
                    shot.id === generation.activeShot?.id ? "active" : ""
                  }
                  type="button"
                  onClick={() => generation.setActiveShotId(shot.id)}
                >
                  <span className="drama-keyframe-shot-thumb">
                    {shot.videoAssetId ? (
                      <video
                        src={mediaAssetUrl(shot.videoAssetId)}
                        muted
                        preload="metadata"
                      />
                    ) : shot.firstFrameAssetId ? (
                      <img
                        src={mediaAssetUrl(shot.firstFrameAssetId)}
                        alt=""
                      />
                    ) : (
                      <Film size={20} />
                    )}
                  </span>
                  <span>
                    <small>
                      {shot.episodeTitle} · 镜 {shot.shotNumber}
                    </small>
                    <strong>{shot.title}</strong>
                    <em>
                      {shot.videoAssetId
                        ? "镜头视频已绑定"
                        : shot.firstFrameAssetId
                          ? "首帧就绪"
                          : "待生成关键帧"}
                    </em>
                  </span>
                  {shot.videoAssetId ? (
                    <CheckCircle2 size={15} />
                  ) : (
                    <ArrowRight size={14} />
                  )}
                </button>
              ))}
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
                    <p>
                      {generation.activeShot.description || "尚未填写镜头描述"}
                    </p>
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
                    <span>视频参考条件</span>
                    <small>
                      {generation.framePair
                        ? "首帧 + 尾帧"
                        : `${generation.sourceImages.length} 张素材`}
                    </small>
                  </div>
                  <div className="drama-clip-frame-row">
                    <FrameCard
                      label="首帧"
                      assetId={generation.activeShot.firstFrameAssetId}
                    />
                    <FrameCard
                      label="尾帧"
                      assetId={generation.activeShot.lastFrameAssetId}
                    />
                    {generation.sourceImages
                      .filter(
                        (assetId) =>
                          assetId !==
                            generation.activeShot?.firstFrameAssetId &&
                          assetId !==
                            generation.activeShot?.lastFrameAssetId,
                      )
                      .slice(0, 7)
                      .map((assetId, index) => (
                        <FrameCard
                          key={assetId}
                          label={`参考 ${index + 1}`}
                          assetId={assetId}
                        />
                      ))}
                  </div>
                  <div className="drama-keyframe-entities">
                    {generation.referencedEntities.map((entity) => (
                      <span key={entity.id}>
                        {entity.name}<small>{entity.kind}</small>
                      </span>
                    ))}
                    {!generation.sourceImages.length && (
                      <small className="drama-clip-context-empty">
                        没有参考帧，将使用文生视频；建议先完成关键帧。
                      </small>
                    )}
                  </div>
                </div>

                <div className="drama-keyframe-controls">
                  <label>
                    <span>视频工作流</span>
                    <select
                      value={generation.selectedModelId}
                      disabled={generation.submitting}
                      onChange={(event) =>
                        generation.setSelectedModelId(event.target.value)
                      }
                    >
                      {generation.videoModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="drama-auto-model-note">
                    <WandSparkles size={14} />
                    <span>{generation.modelReason}</span>
                  </div>
                  <label className="drama-keyframe-prompt">
                    <span>视频提示词</span>
                    <textarea
                      value={generation.prompt}
                      onChange={(event) =>
                        generation.setPrompt(event.target.value)
                      }
                      rows={7}
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
                    ComfyUI 生成视频 {progress ? `${progress}%` : ""}
                    <span>点击停止等待</span>
                  </button>
                ) : (
                  <button
                    className="drama-keyframe-generate"
                    type="button"
                    disabled={
                      !generation.selectedModel ||
                      !generation.prompt.trim() ||
                      !generation.modelCompatible ||
                      generation.missingRequiredParameters.length > 0
                    }
                    onClick={() => void generation.generate()}
                  >
                    <Play size={16} />
                    生成镜头视频
                    <span>{generation.selectedModel?.name ?? "请选择模型"}</span>
                  </button>
                )}
                <div className="drama-clip-generation-summary">
                  <div>
                    <span>工作流模式</span>
                    <strong>
                      {generation.framePair
                        ? "首尾帧驱动"
                        : generation.sourceImages.length
                          ? "多参考生成"
                          : "文生视频"}
                    </strong>
                    <small>{generation.modelReason}</small>
                  </div>
                  <div>
                    <span>参考素材</span>
                    <strong>{generation.sourceImages.length} 张</strong>
                    <small>
                      {generation.referencedEntities.length} 个角色/场景资产
                    </small>
                  </div>
                  <div>
                    <span>提示词状态</span>
                    <strong>
                      {generation.activeShot?.promptOverrides?.video ===
                      generation.prompt
                        ? "已保存版本"
                        : "有未保存修改"}
                    </strong>
                    <small>生成前会自动保存当前版本</small>
                  </div>
                  <div>
                    <span>镜头审核</span>
                    <strong>
                      {generation.activeShot?.status === "approved"
                        ? "导演已通过"
                        : generation.activeShot?.videoAssetId
                          ? "等待人工审核"
                          : "尚未生成视频"}
                    </strong>
                    <small>{generation.activeShot?.durationSeconds}s 成片槽位</small>
                  </div>
                </div>
              </>
            )}
          </section>

          <aside className="drama-keyframe-results">
            <div className="drama-keyframe-panel-title">
              <span>任务与候选</span>
              <small>{resultIds.length} 个视频</small>
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
                      <small>
                        {generation.task.modelName || generation.task.modelId}
                      </small>
                    </span>
                  </div>
                  <div className="drama-keyframe-progress">
                    <span style={{ width: `${progress || 4}%` }} />
                  </div>
                  <code>{generation.task.id.slice(0, 8)}</code>
                </div>
                {resultIds.length ? (
                  <div className="drama-clip-candidates">
                    {resultIds.map((assetId, index) => (
                      <article key={assetId}>
                        <video
                          src={mediaAssetUrl(assetId)}
                          controls
                          preload="metadata"
                        />
                        <div>
                          <span>候选 {String(index + 1).padStart(2, "0")}</span>
                          <button
                            type="button"
                            onClick={() => void generation.attachVideo(assetId)}
                          >
                            设为镜头视频
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="drama-keyframe-task-note">
                    <Layers3 size={20} />
                    <p>视频任务完成后，候选成片会显示在这里。</p>
                  </div>
                )}
              </>
            ) : (
              <div className="drama-keyframe-results-empty">
                <Sparkles size={24} />
                <strong>等待生成</strong>
                <p>提交后显示真实视频任务，并把首张成片自动绑定到镜头。</p>
              </div>
            )}

            <DramaCandidateHistory
              title="镜头视频历史"
              candidates={persistedVideoCandidates}
              mediaType="video"
              busyCandidateId={candidateBusyId}
              onSelect={selectPersistedVideoCandidate}
              onReject={rejectVideoCandidate}
            />

            <div className="drama-clip-current">
              <span>当前镜头视频</span>
              {activeVideoUrl ? (
                <video
                  src={activeVideoUrl}
                  controls
                  preload="metadata"
                />
              ) : (
                <div>
                  <Film size={25} />
                  <small>尚未绑定视频</small>
                </div>
              )}
            </div>

            <div className="drama-clip-frame-actions">
              <button
                type="button"
                disabled={
                  !generation.activeShot?.videoAssetId ||
                  !generation.canExtractFirst ||
                  Boolean(generation.extracting)
                }
                onClick={() => void generation.extractFrame("first")}
              >
                {generation.extracting === "first" ? (
                  <LoaderCircle className="spin" size={14} />
                ) : (
                  <ImageIcon size={14} />
                )}
                提取首帧
              </button>
              <button
                type="button"
                disabled={
                  !generation.activeShot?.videoAssetId ||
                  !generation.canExtractLast ||
                  Boolean(generation.extracting)
                }
                onClick={() => void generation.extractFrame("last")}
              >
                {generation.extracting === "last" ? (
                  <LoaderCircle className="spin" size={14} />
                ) : (
                  <Scissors size={14} />
                )}
                提取尾帧
              </button>
            </div>
            <button
              className="drama-clip-audio-button"
              type="button"
              disabled={
                !generation.activeShot?.videoAssetId ||
                Boolean(generation.extracting)
              }
              onClick={() => void generation.extractAudio()}
            >
              {generation.extracting === "audio" ? (
                <LoaderCircle className="spin" size={14} />
              ) : (
                <Music2 size={14} />
              )}
              从镜头视频提取音频
            </button>
            <button
              className="drama-clip-interpolate-button"
              type="button"
              disabled={
                !generation.activeShot?.videoAssetId || interpolating
              }
              onClick={() => void interpolateVideo()}
            >
              {interpolating ? (
                <LoaderCircle className="spin" size={14} />
              ) : (
                <WandSparkles size={14} />
              )}
              {interpolating ? "RIFE 补帧中" : "补帧至 60fps"}
            </button>
            <button
              className="drama-clip-interpolate-button"
              type="button"
              disabled={
                !generation.activeShot?.videoAssetId || upscalingVideo
              }
              onClick={() => void upscaleShotVideo()}
            >
              {upscalingVideo ? (
                <LoaderCircle className="spin" size={14} />
              ) : (
                <Sparkles size={14} />
              )}
              {upscalingVideo ? "视频超分中" : "超分至 1080p"}
            </button>
            {interpolationError && (
              <p className="drama-clip-action-error">
                {interpolationError}
              </p>
            )}
            {upscaleVideoError && (
              <p className="drama-clip-action-error">
                {upscaleVideoError}
              </p>
            )}
            {generation.extracting && (
              <div className="drama-clip-extract-status">
                <span>
                  正在提取
                  {generation.extracting === "first"
                    ? "首帧"
                    : generation.extracting === "last"
                      ? "尾帧"
                      : "音频"}
                  {extractProgress ? ` · ${extractProgress}%` : ""}
                </span>
              </div>
            )}
            {generation.activeShot?.audioAssetId && (
              <div className="drama-clip-audio-current">
                <span><Music2 size={13} /> 镜头音频</span>
                <audio
                  src={mediaAssetUrl(generation.activeShot.audioAssetId)}
                  controls
                  preload="metadata"
                />
                <button
                  className="drama-audio-normalize"
                  type="button"
                  disabled={normalizingAudio}
                  onClick={() => void normalizeShotAudio()}
                >
                  {normalizingAudio ? (
                    <LoaderCircle className="spin" size={13} />
                  ) : (
                    <AudioLines size={13} />
                  )}
                  {normalizingAudio
                    ? "正在标准化响度"
                    : "标准化为 -16 LUFS"}
                </button>
                <button
                  className="drama-audio-normalize"
                  type="button"
                  disabled={separatingAudio}
                  onClick={() => void separateShotAudio()}
                >
                  {separatingAudio ? (
                    <LoaderCircle className="spin" size={13} />
                  ) : (
                    <Scissors size={13} />
                  )}
                  {separatingAudio
                    ? "正在分离四轨"
                    : "分离人声并绑定"}
                </button>
                <button
                  className="drama-audio-normalize"
                  type="button"
                  disabled={transcribingAudio}
                  onClick={() => void transcribeShotAudio()}
                >
                  {transcribingAudio ? (
                    <LoaderCircle className="spin" size={13} />
                  ) : (
                    <FileText size={13} />
                  )}
                  {transcribingAudio
                    ? "正在生成字幕时间轴"
                    : "转写字幕并加入本集"}
                </button>
                {normalizeAudioError && (
                  <p className="drama-clip-action-error">
                    {normalizeAudioError}
                  </p>
                )}
                {separationAudioError && (
                  <p className="drama-clip-action-error">
                    {separationAudioError}
                  </p>
                )}
                {transcriptionAudioError && (
                  <p className="drama-clip-action-error">
                    {transcriptionAudioError}
                  </p>
                )}
              </div>
            )}

            <div className="drama-clip-tts">
              <div className="drama-clip-tts-head">
                <span><Mic2 size={13} /> 本机中文配音</span>
                <small>
                  {voices.find((voice) => voice.name === voiceName)?.culture ??
                    "Windows SAPI"}
                </small>
              </div>
              <select
                value={voiceName}
                onChange={(event) => setVoiceName(event.target.value)}
              >
                {voices.map((voice) => (
                  <option key={voice.name} value={voice.name}>
                    {voice.name} · {voice.culture}
                  </option>
                ))}
                {!voices.length && (
                  <option value="Microsoft Huihui Desktop">
                    Microsoft Huihui Desktop · zh-CN
                  </option>
                )}
              </select>
              <textarea
                value={ttsText}
                onChange={(event) => setTtsText(event.target.value)}
                rows={3}
                placeholder="输入镜头配音文本…"
              />
              <label>
                <span>
                  语速 {ttsRate > 0 ? "+" : ""}{ttsRate}
                </span>
                <input
                  type="range"
                  min={-5}
                  max={5}
                  step={1}
                  value={ttsRate}
                  onChange={(event) =>
                    setTtsRate(Number(event.target.value))
                  }
                />
              </label>
              <button
                type="button"
                disabled={!ttsText.trim() || ttsGenerating}
                onClick={() => void generateTts()}
              >
                {ttsGenerating ? (
                  <LoaderCircle className="spin" size={14} />
                ) : (
                  <Mic2 size={14} />
                )}
                {ttsGenerating ? "正在生成配音" : "生成并绑定配音"}
              </button>
              {ttsError && <p>{ttsError}</p>}
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
              <RefreshCw size={14} /> 刷新模型与制作状态
            </button>
          </aside>
        </div>
      )}
    </section>
  );
}

function FrameCard({
  label,
  assetId,
}: {
  label: string;
  assetId: string | null | undefined;
}) {
  return (
    <div className={assetId ? "" : "empty"}>
      {assetId ? (
        <img src={mediaAssetUrl(assetId)} alt={label} />
      ) : (
        <Images size={18} />
      )}
      <span>{label}</span>
    </div>
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

function shotStatusLabel(status: string) {
  return {
    planned: "待制作",
    keyframe_ready: "关键帧就绪",
    clip_ready: "视频待审核",
    approved: "已通过",
  }[status] ?? status;
}

function reviewerLabel(reviewer: string) {
  return {
    user: "用户",
    agent: "Agent",
    system: "系统",
  }[reviewer] ?? reviewer;
}

function formatReviewTime(value: string) {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
