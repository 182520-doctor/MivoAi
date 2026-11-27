"use client";

import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clapperboard,
  FileText,
  Film,
  Image as ImageIcon,
  Layers3,
  LocateFixed,
  MapPin,
  Minus,
  Plus,
  ScrollText,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  DramaControlRoom,
  DramaEntityKind,
  DramaEpisode,
  DramaEpisodeAudit,
  DramaEntity,
  DramaSeriesEpisode,
  DramaSeriesOverview,
} from "../../_features/drama/types";
import {
  loadDramaEpisodeAudit,
  loadDramaSeries,
} from "../../_features/drama/api";
import { dramaStages } from "../../_features/drama/productionStages";
import { useDramaAssets } from "../../_features/drama/useDramaAssets";
import { useDramaControlRoom } from "../../_features/drama/useDramaControlRoom";
import { useDramaDocuments } from "../../_features/drama/useDramaDocuments";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";
import { useAppTheme } from "../shell/ThemeProvider";

type DramaCanvasBoardProps = {
  projectId: string;
  projectTitle: string;
  visualStyle: string;
  activeStage: string;
  scope: "global" | "episode";
  selectedEpisodeId: string | null;
  onScopeChange: (scope: "global" | "episode") => void;
  onSelectEpisode: (episodeId: string) => void;
  onOpenStage: (stage: string) => void;
  onOpenShot: (shotId: string, stage: string) => void;
  onOpenAgent: (
    context?: string,
    mode?: "append" | "replace",
  ) => void;
  onScopeContextChange: (context: {
    scope: "global" | "episode" | "stage";
    episodeId: string | null;
    episodeTitle: string | null;
  }) => void;
  refreshToken: number;
};

const documentStages = {
  brief: {
    label: "创意 Brief",
    stage: "brief",
    icon: Sparkles,
  },
  story_bible: {
    label: "故事圣经",
    stage: "bible",
    icon: FileText,
  },
  script: {
    label: "剧本正文",
    stage: "script",
    icon: ScrollText,
  },
} as const;

const entityGroups: Array<{
  kind: DramaEntityKind;
  label: string;
  icon: typeof UserRound;
  stage: string;
}> = [
  { kind: "character", label: "角色", icon: UserRound, stage: "assets" },
  { kind: "location", label: "场景", icon: MapPin, stage: "assets" },
  { kind: "prop", label: "道具", icon: Layers3, stage: "assets" },
  { kind: "style", label: "风格", icon: ImageIcon, stage: "assets" },
];

type InspectedCanvasNode = {
  title: string;
  meta: string;
  ready: boolean;
  onOpen: () => void;
  quickAction?: {
    label: string;
    onClick: () => void;
  };
};

const CanvasInspectionContext = createContext<
  ((node: InspectedCanvasNode | null) => void) | null
>(null);
const CanvasLayoutContext = createContext("");

type DragOffset = { x: number; y: number };
type CanvasConnectionPath = {
  id: string;
  path: string;
};

export function DramaCanvasBoard({
  projectId,
  projectTitle,
  visualStyle,
  activeStage,
  scope,
  selectedEpisodeId,
  onScopeChange,
  onSelectEpisode,
  onOpenStage,
  onOpenShot,
  onOpenAgent,
  onScopeContextChange,
  refreshToken,
}: DramaCanvasBoardProps) {
  const documents = useDramaDocuments(projectId);
  const production = useDramaProduction(projectId);
  const assets = useDramaAssets(projectId);
  const control = useDramaControlRoom(projectId);
  const { theme } = useAppTheme();
  const [view, setView] = useState({ zoom: 0.82, x: 18, y: 10 });
  const [inspectedNode, setInspectedNode] =
    useState<InspectedCanvasNode | null>(null);
  const [panning, setPanning] = useState<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const sceneRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const layoutFrameRef = useRef<number | null>(null);
  const fittedRef = useRef(false);
  const fittedViewportWidthRef = useRef(0);
  const [connectionPaths, setConnectionPaths] = useState<
    CanvasConnectionPath[]
  >([]);
  const [series, setSeries] = useState<DramaSeriesOverview | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;
    async function refreshSeries() {
      try {
        const result = await loadDramaSeries(projectId);
        if (cancelled) return;
        setSeries(result);
        if (result.totals.episodesRunning > 0) {
          timer = window.setTimeout(() => void refreshSeries(), 3000);
        }
      } catch {
        if (!cancelled) setSeries(null);
      }
    }
    void refreshSeries();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [projectId, refreshToken]);

  const assetMap = useMemo(
    () => new Map(assets.assets.map((asset) => [asset.id, asset])),
    [assets.assets],
  );
  const shots = useMemo(
    () =>
      production.episodes.flatMap((episode) =>
        episode.scenes.flatMap((scene) =>
          scene.shots.map((shot) => ({
            ...shot,
            episodeNumber: episode.episodeNumber,
            episodeTitle: episode.title,
            sceneHeading: scene.heading,
          })),
        ),
      ),
    [production.episodes],
  );
  const lockedEntities = assets.entities.filter(
    (entity) => entity.status === "locked",
  ).length;
  const readyShots = shots.filter((shot) => shot.videoAssetId).length;
  const completeEpisodes = production.episodes.filter(
    (episode) => episode.plan?.scenes.length,
  ).length;
  const selectedEpisode =
    production.episodes.find((episode) => episode.id === selectedEpisodeId) ??
    production.episodes[0] ??
    null;
  const episodeShots =
    selectedEpisode?.scenes.flatMap((scene) => scene.shots) ?? [];
  const scopeMetrics =
    scope === "global"
      ? [
          [`${documents.documents.length}`, "文档"],
          [`${assets.entities.length}`, "资产"],
          [`${shots.length}`, "镜头"],
          [`${readyShots}`, "视频"],
        ]
      : [
          [`${selectedEpisode?.scenes.length ?? 0}`, "场次"],
          [`${episodeShots.length}`, "镜头"],
          [
            `${episodeShots.filter((shot) => shot.firstFrameAssetId).length}`,
            "关键帧",
          ],
          [
            `${episodeShots.filter((shot) => shot.videoAssetId).length}`,
            "视频",
          ],
          [
            `${episodeShots.filter((shot) => shot.status === "approved").length}`,
            "已审",
          ],
        ];
  const episodeNumberLabel = `第 ${selectedEpisode?.episodeNumber ?? "-"} 集`;
  const specificEpisodeTitle =
    selectedEpisode?.title
      .replace(
        new RegExp(
          `^第\\s*${selectedEpisode.episodeNumber}\\s*集\\s*[·:：\\-—]*\\s*`,
        ),
        "",
      )
      .trim() ?? "";
  const scopeTitle =
    scope === "global"
      ? `${projectTitle} · 项目总览`
      : specificEpisodeTitle
        ? `${episodeNumberLabel} · ${specificEpisodeTitle}`
        : episodeNumberLabel;

  useEffect(() => {
    onScopeContextChange({
      scope,
      episodeId: scope === "global" ? null : (selectedEpisode?.id ?? null),
      episodeTitle:
        scope === "global" ? null : (selectedEpisode?.title ?? null),
    });
  }, [
    onScopeContextChange,
    scope,
    selectedEpisode?.id,
    selectedEpisode?.title,
  ]);

  useEffect(() => {
    if (!refreshToken) return;
    void documents.refresh();
    void production.refresh();
    void assets.refresh();
    void control.refresh();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const updateConnections = useCallback(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    const sceneRect = scene.getBoundingClientRect();
    const scale = view.zoom || 1;
    const laneOrder = ["script", "episodes", "assets", "shots", "output"];
    const anchors = laneOrder.flatMap((laneName) => {
      const lane = scene.querySelector<HTMLElement>(
        `.drama-canvas-lane.${laneName}`,
      );
      if (!lane) return [];
      const rect = lane.getBoundingClientRect();
      return [
        {
          id: laneName,
          left: (rect.left - sceneRect.left) / scale,
          right: (rect.right - sceneRect.left) / scale,
          centerY: (rect.top - sceneRect.top) / scale + 32,
        },
      ];
    });
    const paths: CanvasConnectionPath[] = [];
    for (let index = 0; index < anchors.length - 1; index += 1) {
      const left = anchors[index];
      const right = anchors[index + 1];
      const x1 = left.right;
      const y1 = left.centerY;
      const x2 = right.left;
      const y2 = right.centerY;
      const bend = Math.max(28, (x2 - x1) * 0.48);
      paths.push({
        id: `${left.id}-${right.id}`,
        path: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${
          x2 - bend
        } ${y2}, ${x2} ${y2}`,
      });
    }
    setConnectionPaths(paths);
  }, [view.zoom]);

  const scheduleConnectionUpdate = useCallback(() => {
    if (layoutFrameRef.current != null) return;
    layoutFrameRef.current = window.requestAnimationFrame(() => {
      layoutFrameRef.current = null;
      updateConnections();
    });
  }, [updateConnections]);

  useEffect(() => {
    scheduleConnectionUpdate();
    const listener = () => scheduleConnectionUpdate();
    window.addEventListener("mivo-canvas-layout", listener);
    window.addEventListener("resize", listener);
    return () => {
      window.removeEventListener("mivo-canvas-layout", listener);
      window.removeEventListener("resize", listener);
      if (layoutFrameRef.current != null) {
        window.cancelAnimationFrame(layoutFrameRef.current);
      }
    };
  }, [scheduleConnectionUpdate]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.round(entry.contentRect.width);
      if (
        width < 240 ||
        Math.abs(width - fittedViewportWidthRef.current) < 40
      ) {
        return;
      }
      fittedViewportWidthRef.current = width;
      window.requestAnimationFrame(() => {
        fitCanvasToViewport();
        fittedRef.current = true;
      });
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const contentCount =
      documents.documents.length +
      production.episodes.length +
      assets.entities.length;
    if (
      scope !== "global" ||
      fittedRef.current ||
      documents.loading ||
      production.loading ||
      assets.loading ||
      contentCount === 0
    ) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      fitCanvasToViewport();
      fittedRef.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
    // Fit once after both the viewport and initial project content are measured.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    scope,
    documents.loading,
    production.loading,
    assets.loading,
    documents.documents.length,
    production.episodes.length,
    assets.entities.length,
  ]);
  function changeZoom(delta: number) {
    setView((current) => ({
      ...current,
      zoom: Math.max(
        0.45,
        Math.min(1.45, Number((current.zoom + delta).toFixed(2))),
      ),
    }));
  }

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if (
      event.button !== 0 ||
      (event.target as HTMLElement).closest(".drama-canvas-node")
    ) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    setPanning({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.x,
      originY: view.y,
    });
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    if (!panning || panning.pointerId !== event.pointerId) return;
    setView((current) => ({
      ...current,
      x: panning.originX + event.clientX - panning.startX,
      y: panning.originY + event.clientY - panning.startY,
    }));
  }

  function endPan(event: React.PointerEvent<HTMLDivElement>) {
    if (!panning || panning.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    setPanning(null);
  }

  function zoomAtWheel(event: React.WheelEvent<HTMLDivElement>) {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    changeZoom(event.deltaY > 0 ? -0.06 : 0.06);
  }

  function fitCanvasToViewport() {
    const viewport = viewportRef.current;
    const scene = sceneRef.current;
    if (!viewport || !scene) return;
    const width = viewport.clientWidth - 28;
    const height = viewport.clientHeight - 28;
    const contentWidth = Math.max(1, scene.offsetWidth);
    const contentHeight = Math.max(1, scene.offsetHeight);
    const compactOverview = viewport.clientWidth < 1100;
    const zoom = Math.max(
      compactOverview ? 0.7 : 0.45,
      Math.min(1.15, width / contentWidth, height / contentHeight),
    );
    setView({
      zoom,
      x: compactOverview
        ? 14
        : Math.max(14, (viewport.clientWidth - contentWidth * zoom) / 2),
      y: Math.max(14, (viewport.clientHeight - contentHeight * zoom) / 2),
    });
  }

  function openSeriesEpisodeAgent(episode: DramaSeriesEpisode) {
    const missing = [
      episode.missingKeyframes.length
        ? `缺少关键帧：${episode.missingKeyframes
            .map((shot) => shot.title)
            .join("、")}`
        : "",
      episode.missingVideos.length
        ? `缺少镜头视频：${episode.missingVideos
            .map((shot) => shot.title)
            .join("、")}`
        : "",
      episode.unreviewedShots.length
        ? `待审核镜头：${episode.unreviewedShots
            .map((shot) => shot.title)
            .join("、")}`
        : "",
    ].filter(Boolean);
    onOpenAgent(
      [
        `继续多集视频生产：项目「${projectTitle}」，第 ${episode.episodeNumber} 集「${episode.title}」。`,
        `项目 ID：${projectId}；分集 ID：${episode.id}。`,
        `当前下一步：${episode.nextActionLabel}；生产队列状态：${episode.queueLabel}。`,
        missing.length ? `当前缺口：${missing.join("；")}。` : "",
        `请先调用 zaojing_get_drama_series 和 zaojing_get_drama_episode，只处理这一集，不要跨集混用镜头或资产。`,
        "先检查本集计划、资产、关键帧和镜头视频的阻断项；只为缺失产物调用 zaojing_plan_drama_production_run 创建待确认任务图。",
        "创建后停下来让我确认，不要自动启动 GPU 批量生成。字幕、剪辑、配音本阶段不做。",
      ]
        .filter(Boolean)
        .join("\n"),
      "replace",
    );
  }

  return (
    <section
      aria-label={`${projectTitle} · ${visualStyle} 制作画布`}
      className={`drama-canvas-board ${
        theme === "light" ? "theme-light" : "theme-dark"
      }`}
    >
      <header className="drama-canvas-toolbar">
        <div className="drama-canvas-context">
          <nav className="drama-canvas-breadcrumb" aria-label="制作范围">
            <button type="button" onClick={() => onScopeChange("global")}>
              项目总览
            </button>
            {scope !== "global" && selectedEpisode && (
              <>
                <ChevronRight size={12} />
                <button
                  type="button"
                  onClick={() => {
                    onSelectEpisode(selectedEpisode.id);
                    onScopeChange("episode");
                  }}
                >
                  第 {selectedEpisode.episodeNumber} 集
                </button>
              </>
            )}
          </nav>
          <strong>{scopeTitle}</strong>
          {scope === "global" && (
            <small>先看项目结构、分集进度与下一步</small>
          )}
        </div>
        <div className="drama-canvas-metrics">
          {scopeMetrics.map(([value, label]) => (
            <span key={label}>
              <strong>{value}</strong>
              {label}
            </span>
          ))}
        </div>
      </header>

      {scope === "global" && series && (
        <section className="drama-series-overview">
          <header>
            <div>
              <span>多集视频生产</span>
              <strong>
                {series.totals.videosReady} / {series.totals.shots} 镜头视频
              </strong>
            </div>
            <div>
              <span>{series.totals.episodes} 集</span>
              <span>{series.totals.plansComplete} 集计划完整</span>
              <span>{series.totals.shotsApproved} 镜已审核</span>
              {series.totals.episodesAwaitingApproval > 0 && (
                <span className="waiting">
                  {series.totals.episodesAwaitingApproval} 集待确认
                </span>
              )}
              {series.totals.episodesRunning > 0 && (
                <span className="running">
                  {series.totals.episodesRunning} 集执行中
                </span>
              )}
              {series.totals.episodesNeedingRetry > 0 && (
                <span className="attention">
                  {series.totals.episodesNeedingRetry} 集需处理
                </span>
              )}
            </div>
          </header>
          <div className="drama-series-episodes">
            {series.episodes.map((episode) => {
              const videoProgress = episode.shotCount
                ? Math.round(
                    (episode.videosReady / episode.shotCount) * 100,
                  )
                : 0;
              return (
                <article
                  key={episode.id}
                  className={`drama-series-episode ${episode.queueState}`}
                >
                  <button
                    className="drama-series-episode-main"
                    type="button"
                    onClick={() => {
                      onSelectEpisode(episode.id);
                      onScopeChange("episode");
                    }}
                  >
                    <div>
                      <span>
                        {String(episode.episodeNumber).padStart(2, "0")}
                      </span>
                      <strong>{episode.title}</strong>
                      <em className={episode.rendered ? "ready" : ""}>
                        {episode.rendered ? "已合成" : episode.nextActionLabel}
                      </em>
                    </div>
                    <div className="drama-series-metrics">
                      <span>
                        <b>{episode.keyframesReady}</b>/{episode.shotCount} 关键帧
                      </span>
                      <span>
                        <b>{episode.videosReady}</b>/{episode.shotCount} 视频
                      </span>
                      <span>
                        <b>{episode.shotsApproved}</b>/{episode.shotCount} 审核
                      </span>
                    </div>
                    <div className="drama-series-progress">
                      <i style={{ width: `${videoProgress}%` }} />
                    </div>
                  </button>
                  <div className="drama-series-episode-footer">
                    <span>{episode.queueLabel}</span>
                    <button
                      type="button"
                      onClick={() => openSeriesEpisodeAgent(episode)}
                    >
                      <Bot size={12} />
                      交给 Agent
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {scope === "global" ? (
        <>
          <div
            ref={viewportRef}
            className={`drama-canvas-viewport ${panning ? "panning" : ""}`}
            onPointerDown={startPan}
            onPointerMove={movePan}
            onPointerUp={endPan}
            onPointerCancel={endPan}
            onWheel={zoomAtWheel}
          >
            <div className="drama-canvas-size">
              <CanvasLayoutContext.Provider
                value={`mivo-drama-canvas:${projectId}`}
              >
                <CanvasInspectionContext.Provider value={setInspectedNode}>
                  <div
                    ref={sceneRef}
                    className="drama-canvas-scene"
                    style={{
                      transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom})`,
                    }}
                  >
                    <div className="drama-canvas-paper-grid" />
                    <svg
                      className="drama-canvas-connections"
                      width="2000"
                      height="1000"
                      viewBox="0 0 2000 1000"
                      aria-hidden="true"
                    >
                      {connectionPaths.map((connection) => (
                        <path key={connection.id} d={connection.path} />
                      ))}
                    </svg>
                    <CanvasLane
                      title="剧本工作区"
                      hint="方向、设定与正文"
                      icon={<ScrollText size={16} />}
                      className="script"
                    >
                      {documents.loading && (
                        <CanvasLoading text="读取剧本文档" />
                      )}
                      {Object.entries(documentStages).map(([kind, meta]) => {
                        const document = documents.documents.find(
                          (item) => item.kind === kind,
                        );
                        const Icon = meta.icon;
                        return (
                          <CanvasNode
                            key={kind}
                            icon={<Icon size={15} />}
                            title={meta.label}
                            meta={
                              document
                                ? `v${document.version} · ${
                                    document.status === "approved"
                                      ? "已审批"
                                      : "草稿"
                                  }`
                                : "尚未创建"
                            }
                            ready={document?.status === "approved"}
                            onClick={() => onOpenStage(meta.stage)}
                          >
                            <p>{documentSummary(document?.content)}</p>
                          </CanvasNode>
                        );
                      })}
                      <CanvasNode
                        icon={<Plus size={15} />}
                        title="与 Agent 确认方向"
                        meta="人工确认门"
                        onClick={onOpenAgent}
                      />
                    </CanvasLane>

                    <CanvasLane
                      title="分集与镜头拆解"
                      hint="集、场、镜头与连续性"
                      icon={<Clapperboard size={16} />}
                      className="episodes"
                    >
                      {production.loading && (
                        <CanvasLoading text="读取制作图谱" />
                      )}
                      {production.episodes.slice(0, 4).map((episode) => (
                        <CanvasNode
                          key={episode.id}
                          icon={<Clapperboard size={15} />}
                          title={`第 ${episode.episodeNumber} 集 · ${episode.title}`}
                          meta={`${episode.scenes.length} 场 · ${episode.scenes.reduce(
                            (count, scene) => count + scene.shots.length,
                            0,
                          )} 镜`}
                          ready={Boolean(episode.plan?.scenes.length)}
                          onClick={() => onOpenStage("breakdown")}
                        >
                          <p>
                            {episode.plan?.storyBeats.join(" → ") ||
                              episode.synopsis ||
                              "尚未完成逐集故事拆解"}
                          </p>
                          <div className="drama-canvas-chip-row">
                            <span>{episode.plan?.timeScope || "时间待定"}</span>
                            <span>
                              {episode.plan?.interiorExterior.join(" / ") ||
                                "内外景待定"}
                            </span>
                          </div>
                        </CanvasNode>
                      ))}
                      {!production.episodes.length && !production.loading && (
                        <CanvasNode
                          icon={<Plus size={15} />}
                          title="创建第一集"
                          meta="从已审批剧本拆解"
                          onClick={() => onOpenStage("breakdown")}
                        />
                      )}
                      <CanvasNode
                        icon={<CheckCircle2 size={15} />}
                        title="分集检查"
                        meta={`${completeEpisodes} / ${production.episodes.length} 集计划完整`}
                        ready={
                          production.episodes.length > 0 &&
                          completeEpisodes === production.episodes.length
                        }
                        onClick={() => onOpenStage("breakdown")}
                      />
                    </CanvasLane>

                    <CanvasLane
                      title="制作资产库"
                      hint="角色、场景、道具与风格"
                      icon={<ImageIcon size={16} />}
                      className="assets"
                    >
                      {assets.loading && <CanvasLoading text="读取资产库" />}
                      {entityGroups.map((group) => {
                        const entities = assets.entities.filter(
                          (entity) => entity.kind === group.kind,
                        );
                        const Icon = group.icon;
                        return (
                          <CanvasNode
                            key={group.kind}
                            icon={<Icon size={15} />}
                            title={group.label}
                            meta={`${entities.length} 个 · ${
                              entities.filter(
                                (entity) => entity.status === "locked",
                              ).length
                            } 个已锁定`}
                            ready={
                              entities.length > 0 &&
                              entities.every(
                                (entity) => entity.status === "locked",
                              )
                            }
                            onClick={() => onOpenStage(group.stage)}
                          >
                            <div className="drama-canvas-assets">
                              {entities.slice(0, 5).map((entity) => {
                                const primary = entity.primaryAssetId
                                  ? assetMap.get(entity.primaryAssetId)
                                  : null;
                                return (
                                  <span key={entity.id} title={entity.name}>
                                    {primary ? (
                                      <img
                                        src={backendResourceUrl(primary.url)}
                                        alt={entity.name}
                                      />
                                    ) : (
                                      <Icon size={15} />
                                    )}
                                    <small>{entity.name}</small>
                                  </span>
                                );
                              })}
                              {!entities.length && (
                                <p>尚未规划{group.label}资产</p>
                              )}
                            </div>
                          </CanvasNode>
                        );
                      })}
                      <div className="drama-canvas-lock-summary">
                        <CheckCircle2 size={14} />
                        {lockedEntities} 个资产已锁定
                      </div>
                    </CanvasLane>

                    <CanvasLane
                      title="镜头与画面"
                      hint="首尾帧、九宫格、故事板"
                      icon={<Film size={16} />}
                      className="shots"
                    >
                      {shots.slice(0, 5).map((shot) => {
                        const frame = shot.firstFrameAssetId
                          ? assetMap.get(shot.firstFrameAssetId)
                          : null;
                        return (
                          <CanvasNode
                            key={shot.id}
                            icon={<Film size={15} />}
                            title={`镜 ${shot.shotNumber} · ${shot.title}`}
                            meta={`第 ${shot.episodeNumber} 集 · ${shot.durationSeconds}s`}
                            ready={Boolean(shot.videoAssetId)}
                            onClick={() =>
                              onOpenShot(
                                shot.id,
                                shot.videoAssetId ? "clips" : "keyframes",
                              )
                            }
                            quickAction={{
                              label: shot.videoAssetId
                                ? "打开该镜头视频"
                                : "打开该镜头关键帧",
                              onClick: () =>
                                onOpenShot(
                                  shot.id,
                                  shot.videoAssetId ? "clips" : "keyframes",
                                ),
                            }}
                          >
                            <div className="drama-canvas-shot">
                              <span>
                                {frame ? (
                                  <img
                                    src={backendResourceUrl(frame.url)}
                                    alt={shot.title}
                                  />
                                ) : (
                                  <ImageIcon size={20} />
                                )}
                              </span>
                              <div>
                                <p>{shot.description || "尚未填写画面描述"}</p>
                                <em>
                                  {shot.videoAssetId
                                    ? "视频已生成"
                                    : shot.firstFrameAssetId
                                      ? "关键帧已绑定"
                                      : "等待关键帧"}
                                </em>
                              </div>
                            </div>
                          </CanvasNode>
                        );
                      })}
                      {!shots.length && !production.loading && (
                        <CanvasNode
                          icon={<Plus size={15} />}
                          title="还没有镜头"
                          meta="先完成分集和场次拆解"
                          onClick={() => onOpenStage("breakdown")}
                        />
                      )}
                      <CanvasNode
                        icon={<ArrowRight size={15} />}
                        title="进入关键帧工作区"
                        meta="生成首帧、尾帧、九宫格与故事板"
                        onClick={() => onOpenStage("keyframes")}
                      />
                    </CanvasLane>

                    <CanvasLane
                      title="后期输出"
                      hint="声音、字幕、时间线与成片"
                      icon={<Clapperboard size={16} />}
                      className="output"
                    >
                      <CanvasNode
                        icon={<Film size={15} />}
                        title="镜头视频与声音"
                        meta={`${readyShots} / ${shots.length} 镜有视频`}
                        ready={shots.length > 0 && readyShots === shots.length}
                        onClick={() => onOpenStage("clips")}
                      />
                      <CanvasNode
                        icon={<Clapperboard size={15} />}
                        title="整集时间线"
                        meta={`${
                          production.episodes.filter(
                            (episode) => episode.status === "rendered",
                          ).length
                        } / ${production.episodes.length} 集已导出`}
                        ready={
                          production.episodes.length > 0 &&
                          production.episodes.every(
                            (episode) => episode.status === "rendered",
                          )
                        }
                        onClick={() => onOpenStage("timeline")}
                      />
                      <CanvasNode
                        icon={
                          shots.length > 0 && readyShots === shots.length ? (
                            <CheckCircle2 size={15} />
                          ) : (
                            <CircleAlert size={15} />
                          )
                        }
                        title="制作检查"
                        meta={
                          shots.length && readyShots === shots.length
                            ? "镜头视频已齐"
                            : "仍有镜头未完成"
                        }
                        onClick={() => onOpenStage("timeline")}
                      />
                    </CanvasLane>
                  </div>
                </CanvasInspectionContext.Provider>
              </CanvasLayoutContext.Provider>
            </div>
          </div>

          {inspectedNode && (
            <aside className="drama-canvas-inspector">
              <header>
                <div>
                  <span>节点属性</span>
                  <strong>{inspectedNode.title}</strong>
                </div>
                <button
                  type="button"
                  aria-label="关闭节点属性"
                  onClick={() => setInspectedNode(null)}
                >
                  <X size={15} />
                </button>
              </header>
              <div className="drama-canvas-inspector-body">
                <span className={inspectedNode.ready ? "ready" : ""}>
                  {inspectedNode.ready ? "已就绪" : "待完成"}
                </span>
                <p>{inspectedNode.meta}</p>
                <small>
                  画布只负责全局关系。进入编辑后，修改仍会写回同一个项目数据。
                </small>
              </div>
              {inspectedNode.quickAction && (
                <button
                  className="drama-canvas-inspector-quick"
                  type="button"
                  onClick={() => {
                    inspectedNode.quickAction?.onClick();
                    setInspectedNode(null);
                  }}
                >
                  {inspectedNode.quickAction.label}
                </button>
              )}
              <button
                className="drama-canvas-inspector-open"
                type="button"
                onClick={() => {
                  inspectedNode.onOpen();
                  setInspectedNode(null);
                }}
              >
                进入详细编辑 <ArrowRight size={14} />
              </button>
            </aside>
          )}
        </>
      ) : (
        <EpisodeScopeBoard
          selectedEpisode={selectedEpisode}
          controlRoom={control.controlRoom}
          documents={documents.documents}
          assetCount={assets.entities.length}
          onOpenStage={onOpenStage}
          onOpenAgent={onOpenAgent}
          refreshToken={refreshToken}
        />
      )}

      {scope === "global" && (
        <footer className="drama-canvas-zoom">
          <span className="drama-canvas-hint">
            拖动空白处平移 · Ctrl/⌘ + 滚轮缩放
          </span>
          <button type="button" onClick={() => changeZoom(-0.08)}>
            <Minus size={14} />
          </button>
          <span>{Math.round(view.zoom * 100)}%</span>
          <button type="button" onClick={() => changeZoom(0.08)}>
            <Plus size={14} />
          </button>
          <button type="button" onClick={fitCanvasToViewport}>
            <LocateFixed size={14} /> 适应
          </button>
          <button
            type="button"
            onClick={() => {
              const prefix = `mivo-drama-canvas:${projectId}`;
              for (
                let index = localStorage.length - 1;
                index >= 0;
                index -= 1
              ) {
                const key = localStorage.key(index);
                if (key?.startsWith(prefix)) localStorage.removeItem(key);
              }
              window.location.reload();
            }}
          >
            重置节点
          </button>
        </footer>
      )}
    </section>
  );
}

function EpisodeScopeBoard({
  selectedEpisode,
  controlRoom,
  documents,
  assetCount,
  onOpenStage,
  onOpenAgent,
  refreshToken,
}: {
  selectedEpisode: DramaEpisode | null;
  controlRoom: DramaControlRoom | null;
  documents: Array<{ kind: string; status: string }>;
  assetCount: number;
  onOpenStage: (stage: string) => void;
  onOpenAgent: (
    context?: string,
    mode?: "append" | "replace",
  ) => void;
  refreshToken: number;
}) {
  const [audit, setAudit] = useState<DramaEpisodeAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  useEffect(() => {
    if (!selectedEpisode) {
      setAudit(null);
      setAuditLoading(false);
      return;
    }
    let cancelled = false;
    setAuditLoading(true);
    void loadDramaEpisodeAudit(selectedEpisode.id)
      .then((result) => {
        if (!cancelled) setAudit(result);
      })
      .catch(() => {
        if (!cancelled) setAudit(null);
      })
      .finally(() => {
        if (!cancelled) setAuditLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedEpisode?.id, refreshToken]);

  if (!selectedEpisode) {
    return (
      <div className="drama-scope-empty">
        <Clapperboard size={28} />
        <strong>还没有分集</strong>
        <p>先完成剧本，再让 Agent 按集拆解时间、人物、场景和故事。</p>
        <button type="button" onClick={() => onOpenStage("breakdown")}>
          创建分集
        </button>
      </div>
    );
  }
  const shots = selectedEpisode.scenes.flatMap((scene) => scene.shots);
  const plan = selectedEpisode.plan;
  const planFields = [
    ["时间", plan?.timeScope || "待拆解"],
    ["地点", plan?.locations.join("、") || "待拆解"],
    ["内外景", plan?.interiorExterior.join("、") || "待拆解"],
    ["人物", plan?.characters.join("、") || "待拆解"],
    ["场景", plan?.scenes.join("、") || "待拆解"],
    ["故事", plan?.storyBeats.join(" → ") || "待拆解"],
    ["画面", plan?.visualRequirements.join("；") || "待检查"],
    ["对白", plan?.dialogueRequirements.join("；") || "待检查"],
  ];
  const planGaps = planFields.filter(([, value]) => value.startsWith("待"));
  const primaryPlanLabels = new Set(["时间", "地点", "人物", "故事"]);
  const primaryPlanFields = planFields.filter(([label]) =>
    primaryPlanLabels.has(label),
  );
  const secondaryPlanFields = planFields.filter(
    ([label]) => !primaryPlanLabels.has(label),
  );
  const sceneContracts = plan?.sceneContracts ?? [];
  const episodePlan = controlRoom?.episodes.find(
    (item) => item.id === selectedEpisode.id,
  );
  const documentReady = (kind: string) =>
    documents.some(
      (document) => document.kind === kind && document.status === "approved",
    );
  const visibleIssues = audit?.issues.slice(0, 2) ?? [];
  const auditTone = audit?.errorCount
    ? "failed"
    : audit?.warningCount
      ? "warning"
      : "passed";

  return (
    <div className="drama-scope-board drama-episode-scope compact">
      <section className="drama-scope-main">
        <div className="drama-episode-lead">
          <p>{selectedEpisode.synopsis || "尚未填写本集梗概"}</p>
          <div>
            <span className={episodePlan?.planComplete ? "ready" : ""}>
              {episodePlan?.planComplete
                ? "本集计划完整"
                : `本集计划还缺 ${planGaps.length} 项`}
            </span>
            {plan?.continuityRisks.length ? (
              <span className="risk">
                {plan.continuityRisks.length} 项连续性风险
              </span>
            ) : null}
            <button
              type="button"
              onClick={() =>
                onOpenAgent(
                  `当前范围是第 ${selectedEpisode.episodeNumber} 集《${selectedEpisode.title}》。` +
                    "请检查本集时间、地点、人物、场景、故事节拍、画面、对白和连续性，" +
                    `当前明确缺口：${
                      planGaps.length
                        ? planGaps.map(([label]) => label).join("、")
                        : "拆解字段已填写，请复核冲突"
                    }。` +
                    "先指出缺失与冲突，再提出下一项明确产物。",
                )
              }
            >
              <Bot size={14} /> Agent 检查本集
            </button>
          </div>
        </div>

        <div className="drama-episode-overview-grid">
          <section className="drama-episode-plan-block">
            <header>
              <strong>本集拆解</strong>
              <em className={planGaps.length ? "" : "ready"}>
                {planGaps.length
                  ? `${planGaps.length} 项待补`
                  : "关键字段已填写"}
              </em>
            </header>
            <div className="drama-episode-plan-fields primary">
              {primaryPlanFields.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <details className="drama-episode-plan-more">
              <summary>更多拆解：内外景、场景、画面与对白</summary>
              <div className="drama-episode-plan-fields secondary">
                {secondaryPlanFields.map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
            </details>
          </section>

          <section className="drama-episode-contract-block">
            <header>
              <strong>场景与连续性</strong>
              <em className={sceneContracts.length ? "ready" : ""}>
                {sceneContracts.length
                  ? `${sceneContracts.length} 场已结构化`
                  : "场景契约待建立"}
              </em>
            </header>
            {sceneContracts.length ? (
              <div className="drama-episode-contract-preview">
                {sceneContracts.slice(0, 3).map((contract) => (
                  <article key={contract.sceneNumber}>
                    <strong>
                      场 {contract.sceneNumber}
                      {contract.title ? ` · ${contract.title}` : ""}
                    </strong>
                    <span>
                      {contract.valueIn || "起始价值"} →{" "}
                      {contract.valueOut || "退出价值"}
                    </span>
                    <small>
                      {contract.characterObjectives.join("；") ||
                        contract.obstacle ||
                        "待补人物目标与障碍"}
                    </small>
                  </article>
                ))}
              </div>
            ) : (
              <p>
                还没有逐场目标、障碍、转折与表演策略。Agent
                建立后才能稳定生成资产和镜头。
              </p>
            )}
            {plan?.continuityRisks.length ? (
              <div className="drama-episode-risk-list">
                <span>连续性风险</span>
                {plan.continuityRisks.slice(0, 3).map((risk) => (
                  <small key={risk}>{risk}</small>
                ))}
              </div>
            ) : null}
            <button
              type="button"
              onClick={() =>
                onOpenAgent(
                  `请为第 ${selectedEpisode.episodeNumber} 集建立或完善逐场创作契约。` +
                    "读取专业故事规范，为每场写清进入价值、人物目标、障碍、战术、节拍、转折、退出价值、潜台词、声台形表、视觉与声音策略。" +
                    "完成后调用 zaojing_audit_drama_episode 自审并修复问题，再提交给我审核。",
                  "replace",
                )
              }
            >
              <Bot size={14} />
              {sceneContracts.length ? "让 Agent 完善场景契约" : "让 Agent 建立场景契约"}
            </button>
          </section>
        </div>

        <section className={`drama-episode-audit ${auditTone}`}>
          <header>
            <div>
              <CircleAlert size={16} />
              <strong>本集质量检查</strong>
              {auditLoading ? (
                <small>正在检查…</small>
              ) : audit ? (
                <>
                  <em>{audit.score} 分</em>
                  <span>{audit.errorCount} 错误</span>
                  <span>{audit.warningCount} 警告</span>
                </>
              ) : (
                <small>检查结果暂不可用</small>
              )}
            </div>
            <div>
              {audit && (
                <small>
                  {audit.readyForAssets
                    ? "上游检查无阻断错误"
                    : "存在阻断后续制作的错误"}
                </small>
              )}
              <button
                type="button"
                onClick={() =>
                  onOpenAgent(
                    `请只处理当前第 ${selectedEpisode.episodeNumber} 集的质量检查问题。` +
                      `当前错误：${audit?.errorCount ?? "未知"}，警告：${audit?.warningCount ?? "未知"}。` +
                      `优先项：${
                        visibleIssues
                          .map((issue) => issue.message)
                          .join("；") ||
                        "请先调用 zaojing_audit_drama_episode 获取最新结果"
                      }。` +
                      "先说明需要用户决策的内容；不要自动审批，也不要启动昂贵生成。",
                  )
                }
              >
                <Bot size={14} /> Agent 处理检查项
              </button>
            </div>
          </header>
          {visibleIssues.length > 0 && (
            <div className="drama-episode-audit-issues">
              {visibleIssues.map((issue, index) => (
                <span
                  key={`${issue.code}-${
                    issue.shotId ?? issue.entityId ?? "episode"
                  }-${index}`}
                  className={issue.severity}
                >
                  {issue.severity === "error"
                    ? "阻断"
                    : issue.severity === "warning"
                      ? "警告"
                      : "提示"}
                  ：{issue.message}
                </span>
              ))}
              {(audit?.issues.length ?? 0) > visibleIssues.length && (
                <small>
                  另有 {(audit?.issues.length ?? 0) - visibleIssues.length}{" "}
                  项，可在 Agent 中查看全部
                </small>
              )}
            </div>
          )}
        </section>

        <div className="drama-episode-artifacts">
          <header>
            <span>本集产物链</span>
            <small>点击进入具体阶段</small>
          </header>
          <div>
            {dramaStages.map((stage) => {
              const Icon = stage.icon;
              const produced = episodeArtifactReady(
                stage.id,
                selectedEpisode,
                shots,
                documentReady,
                assetCount,
              );
              return (
                <button
                  key={stage.id}
                  className={produced ? "ready" : ""}
                  type="button"
                  onClick={() => onOpenStage(stage.id)}
                >
                  <Icon size={15} />
                  <div>
                    <strong>{stage.deliverable}</strong>
                    <small>{stage.artifacts.join(" · ")}</small>
                  </div>
                  {produced ? (
                    <CheckCircle2 size={14} />
                  ) : (
                    <ArrowRight size={13} />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}

function CanvasLane({
  title,
  hint,
  icon,
  className,
  children,
}: {
  title: string;
  hint: string;
  icon: React.ReactNode;
  className: string;
  children: React.ReactNode;
}) {
  const layoutPrefix = useContext(CanvasLayoutContext);
  const storageKey = `${layoutPrefix}:lane:${className}`;
  const [offset, setOffset] = useState<DragOffset>(() =>
    readCanvasOffset(storageKey),
  );
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  function pointerDown(event: React.PointerEvent<HTMLElement>) {
    if (event.button !== 0) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: offset.x,
      originY: offset.y,
    };
    setDragging(true);
  }

  function pointerMove(event: React.PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setOffset({
      x: drag.originX + event.clientX - drag.startX,
      y: drag.originY + event.clientY - drag.startY,
    });
    window.dispatchEvent(new Event("mivo-canvas-layout"));
  }

  function pointerUp(event: React.PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    const finalOffset = {
      x: drag.originX + event.clientX - drag.startX,
      y: drag.originY + event.clientY - drag.startY,
    };
    setOffset(finalOffset);
    writeCanvasOffset(storageKey, finalOffset);
    window.dispatchEvent(new Event("mivo-canvas-layout"));
    dragRef.current = null;
    setDragging(false);
  }

  return (
    <section
      className={`drama-canvas-lane ${className} ${dragging ? "dragging" : ""}`}
      style={{
        transform: `translate(${offset.x}px, ${offset.y}px)`,
        zIndex: dragging ? 4 : 1,
      }}
    >
      <header
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerUp}
      >
        <span>{icon}</span>
        <div>
          <strong>{title}</strong>
          <small>{hint}</small>
        </div>
      </header>
      <div className="drama-canvas-node-stack">{children}</div>
    </section>
  );
}

function CanvasNode({
  icon,
  title,
  meta,
  ready = false,
  onClick,
  quickAction,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  meta: string;
  ready?: boolean;
  onClick: () => void;
  quickAction?: {
    label: string;
    onClick: () => void;
  };
  children?: React.ReactNode;
}) {
  const inspect = useContext(CanvasInspectionContext);
  const layoutPrefix = useContext(CanvasLayoutContext);
  const storageKey = `${layoutPrefix}:node:${encodeURIComponent(title)}`;
  const [offset, setOffset] = useState<DragOffset>(() =>
    readCanvasOffset(storageKey),
  );
  const [dragging, setDragging] = useState(false);
  const draggedRef = useRef(false);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
  } | null>(null);

  useEffect(() => {
    setOffset(readCanvasOffset(storageKey));
  }, [storageKey]);

  function pointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    draggedRef.current = false;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: offset.x,
      originY: offset.y,
      moved: false,
    };
  }

  function pointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 5) {
      drag.moved = true;
      draggedRef.current = true;
      setDragging(true);
    }
    if (drag.moved) {
      setOffset({ x: drag.originX + dx, y: drag.originY + dy });
      window.dispatchEvent(new Event("mivo-canvas-layout"));
    }
  }

  function pointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (drag.moved) {
      const finalOffset = {
        x: drag.originX + event.clientX - drag.startX,
        y: drag.originY + event.clientY - drag.startY,
      };
      setOffset(finalOffset);
      writeCanvasOffset(storageKey, finalOffset);
      window.dispatchEvent(new Event("mivo-canvas-layout"));
    }
    dragRef.current = null;
    setDragging(false);
  }

  return (
    <button
      className={`drama-canvas-node ${ready ? "ready" : ""} ${
        dragging ? "dragging" : ""
      }`}
      type="button"
      style={{
        transform: `translate(${offset.x}px, ${offset.y}px)`,
        zIndex: dragging ? 5 : undefined,
      }}
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={pointerUp}
      onPointerCancel={pointerUp}
      onClick={() => {
        if (draggedRef.current) {
          draggedRef.current = false;
          return;
        }
        if (inspect) {
          inspect({
            title,
            meta,
            ready,
            onOpen: onClick,
            quickAction,
          });
        } else {
          onClick();
        }
      }}
    >
      <div className="drama-canvas-node-head">
        <span>{icon}</span>
        <div>
          <strong>{title}</strong>
          <small>{meta}</small>
        </div>
        {ready ? <CheckCircle2 size={14} /> : <ArrowRight size={13} />}
      </div>
      {children && <div className="drama-canvas-node-body">{children}</div>}
    </button>
  );
}

function CanvasLoading({ text }: { text: string }) {
  return <div className="drama-canvas-loading">{text}…</div>;
}

function documentSummary(content: string | undefined) {
  const text = (content || "").replace(/\s+/g, " ").trim();
  if (!text) return "等待 Agent 或用户开始编写";
  return text.length > 88 ? `${text.slice(0, 88)}…` : text;
}

function episodeArtifactReady(
  stageId: string,
  episode: DramaEpisode,
  shots: DramaEpisode["scenes"][number]["shots"],
  documentReady: (kind: string) => boolean,
  assetCount: number,
) {
  if (stageId === "brief") return documentReady("brief");
  if (stageId === "bible") return documentReady("story_bible");
  if (stageId === "script") return documentReady("script");
  if (stageId === "breakdown") return Boolean(episode.plan?.scenes.length);
  if (stageId === "assets") return assetCount > 0;
  if (stageId === "keyframes") {
    return shots.length > 0 && shots.every((shot) => shot.firstFrameAssetId);
  }
  if (stageId === "clips") {
    return shots.length > 0 && shots.every((shot) => shot.videoAssetId);
  }
  return episode.status === "rendered";
}

function readCanvasOffset(storageKey: string): DragOffset {
  if (typeof window === "undefined") return { x: 0, y: 0 };
  try {
    const value = JSON.parse(
      localStorage.getItem(storageKey) || "{}",
    ) as Partial<DragOffset>;
    return {
      x: Number(value.x) || 0,
      y: Number(value.y) || 0,
    };
  } catch {
    return { x: 0, y: 0 };
  }
}

function writeCanvasOffset(storageKey: string, offset: DragOffset) {
  if (typeof window === "undefined") return;
  localStorage.setItem(storageKey, JSON.stringify(offset));
}
