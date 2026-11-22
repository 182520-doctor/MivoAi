"use client";

import {
  ArrowRight,
  BookOpenText,
  CheckCircle2,
  Clapperboard,
  Clock3,
  FolderKanban,
  Image as ImageIcon,
  Plus,
  ScrollText,
  Sparkles,
  SplitSquareVertical,
  WandSparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { DramaDocumentKind } from "../../_features/drama/types";
import {
  dramaPhases as phases,
  dramaStages as stages,
} from "../../_features/drama/productionStages";
import { useDramaDocuments } from "../../_features/drama/useDramaDocuments";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";
import { useDramaProjects } from "../../_features/drama/useDramaProjects";
import { DramaAssetBoard } from "./DramaAssetBoard";
import { DramaAgentPanel } from "./DramaAgentPanel";
import { DramaCanvasBoard } from "./DramaCanvasBoard";
import { DramaClipBoard } from "./DramaClipBoard";
import { DramaControlRoom } from "./DramaControlRoom";
import { DramaKeyframeBoard } from "./DramaKeyframeBoard";
import { DramaProductionBoard } from "./DramaProductionBoard";
import { DramaScriptWorkspace } from "./DramaScriptWorkspace";
import { DramaScopeNavigator } from "./DramaScopeNavigator";
import { DramaTimelineBoard } from "./DramaTimelineBoard";

const styles = ["电影写实", "东方古风", "悬疑冷调", "都市情感"];
const storySeeds = [
  {
    label: "古风悬疑",
    idea: "一位宋朝公主发现宫廷画师偷偷记录了她的另一重身份，她必须在身份暴露前找回被改写的记忆。",
    style: "东方古风",
    format: "9:16",
  },
  {
    label: "都市反转",
    idea: "一个每天替别人道歉的客服，意外收到一封来自未来、收件人是自己的道歉信。",
    style: "都市情感",
    format: "9:16",
  },
  {
    label: "冷调犯罪",
    idea: "雨夜里，一名失忆刑警在案发现场发现了自己的指纹，而监控中的凶手正向他发出求救。",
    style: "悬疑冷调",
    format: "16:9",
  },
] as const;
const documentKindByStage: Partial<Record<string, DramaDocumentKind>> = {
  brief: "brief",
  bible: "story_bible",
  script: "script",
};

export function DramaWorkbench() {
  const drama = useDramaProjects();
  const documents = useDramaDocuments(drama.project?.id ?? null);
  const production = useDramaProduction(drama.project?.id ?? null);
  const [idea, setIdea] = useState("");
  const [format, setFormat] = useState("9:16");
  const [style, setStyle] = useState(styles[0]);
  const [creating, setCreating] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [viewMode, setViewMode] = useState<"canvas" | "flow">("canvas");
  const [targetShotId, setTargetShotId] = useState<string | null>(null);
  const [workspaceVersion, setWorkspaceVersion] = useState(0);
  const [canvasScope, setCanvasScope] = useState<
    "global" | "episode" | "stage"
  >("global");
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(
    null,
  );
  const [embeddedAgentPrompt, setEmbeddedAgentPrompt] = useState("");
  const [agentContext, setAgentContext] = useState<{
    scope: "global" | "episode" | "stage";
    episodeId: string | null;
    episodeTitle: string | null;
  }>({ scope: "global", episodeId: null, episodeTitle: null });
  const project = drama.project;
  const activeStage = project?.activeStage ?? stages[0].id;
  const selected =
    stages.find((stage) => stage.id === activeStage) ?? stages[0];
  const Icon = selected.icon;
  const activeIndex = stages.findIndex((stage) => stage.id === activeStage);
  const documentKind = documentKindByStage[activeStage];
  const activePhase =
    phases.find((phase) => phase.stages.includes(activeStage as never)) ??
    phases[0];
  const phaseStages = stages.filter((stage) =>
    activePhase.stages.includes(stage.id as never),
  );
  const activeDocument = documentKind
    ? (documents.documents.find((document) => document.kind === documentKind) ??
      null)
    : null;
  const productionFocusedStage = [
    "assets",
    "keyframes",
    "clips",
    "timeline",
  ].includes(activeStage);

  useEffect(() => {
    if (!documentKind) {
      setDraftContent("");
      return;
    }
    setDraftContent(
      activeDocument?.content ??
        documentTemplate(documentKind, project?.idea ?? ""),
    );
  }, [activeDocument?.content, documentKind, project?.idea]);

  useEffect(() => {
    if (!workspaceVersion) return;
    void production.refresh();
    void documents.refresh();
    void drama.refresh();
    // The token is emitted once after a mutating Agent tool completes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceVersion]);

  async function createDraft() {
    const normalized = idea.trim();
    if (!normalized) return;
    const created = await drama.create({
      idea: normalized,
      format,
      visualStyle: style,
    });
    if (created) {
      setCreating(false);
      setIdea("");
    }
  }

  function beginNewProject() {
    drama.selectProject(null);
    setCreating(true);
    setIdea("");
  }

  async function saveStageDocument() {
    if (!documentKind || !project) return;
    await documents.save(
      documentKind,
      activeDocument?.title ??
        {
          brief: "项目创作说明",
          story_bible: "故事圣经",
          script: "剧本",
        }[documentKind],
      draftContent,
    );
  }

  function openAgentForStage(
    context?: string,
    mode: "append" | "replace" = "append",
  ) {
    if (!project || !selected) return;
    const prompt =
      mode === "replace"
        ? (context?.trim() ?? "")
        : [
            `继续 MivoAi 短剧项目「${project.title}」，当前阶段是 ${selected.label}（${activeStage}）。`,
            context || "",
            `请先调用 zaojing_get_drama_control_room 读取项目状态，再调用 zaojing_get_drama_roles 获取本阶段角色手册。`,
            `本阶段交付物是：${selected.deliverable}。`,
            activeStage === "brief" || activeStage === "bible"
              ? "只在这一轮集中确认一次故事命题、受众、集数、单集时长、内容边界和视觉方向；确认后由你承担后续专业创作，不要反复要求我填写表单。"
              : "AI 主导执行：读取已确认的方向和当前真实数据，直接完成本阶段专业草稿、按角色清单自审并修复明显问题，最后把可审核版本和关键取舍交给我。",
            "除重大不可逆创意分歧、版权/内容边界、昂贵模型成本或我明确否决外，不要停下来让我逐项配置专业内容。",
            "草稿只能通过短剧工具保存为待审版本，不要声称已经由我批准，也不要未经确认启动昂贵的图片或视频批量生成。",
            `完成后用 zaojing_review_drama_stage 让相关角色逐项审核，并明确告诉我哪些问题需要我决定。项目 ID：${project.id}`,
          ]
            .filter(Boolean)
            .join("\n");
    setEmbeddedAgentPrompt(prompt);
  }

  function selectPhase(phase: (typeof phases)[number]) {
    if (!project) return;
    setViewMode("flow");
    if (phase.stages.includes(activeStage as never)) return;
    void drama.updateStage(project.id, phase.stages[0]);
  }

  function openCanvasStage(stage: string) {
    if (!project) return;
    setViewMode("flow");
    if (stage !== activeStage) {
      void drama.updateStage(project.id, stage);
    }
  }

  function selectGlobalScope() {
    setCanvasScope("global");
    setViewMode("canvas");
    setAgentContext({ scope: "global", episodeId: null, episodeTitle: null });
  }

  function selectEpisodeScope(episodeId: string) {
    const episode = production.episodes.find((item) => item.id === episodeId);
    setSelectedEpisodeId(episodeId);
    setCanvasScope("episode");
    setViewMode("canvas");
    setAgentContext({
      scope: "episode",
      episodeId,
      episodeTitle: episode?.title ?? null,
    });
  }

  function selectStageScope(stageId: string) {
    setCanvasScope("stage");
    setViewMode("canvas");
    if (stageId !== activeStage) {
      void drama.updateStage(project?.id ?? "", stageId);
    }
    setAgentContext({
      scope: "stage",
      episodeId: selectedEpisodeId,
      episodeTitle:
        production.episodes.find((episode) => episode.id === selectedEpisodeId)
          ?.title ?? null,
    });
  }

  function openCanvasShot(shotId: string, stage: string) {
    setTargetShotId(shotId);
    openCanvasStage(stage);
  }

  return (
    <main className="drama-studio-page">
      <h1 className="visually-hidden">短剧制作</h1>
      {!project || creating ? (
        <>
          <section className="drama-quickstart">
            <div className="drama-quickstart-copy">
              <span className="eyebrow">
                <Sparkles size={13} />
                AI 短剧制作台
              </span>
              <h2>
                把一个念头，
                <em>拍成一部短剧。</em>
              </h2>
              <p>
                从故事方向开始，Agent 会协助你完成设定、剧本、资产、分镜和成片。
                每一步都有版本与人工确认。
              </p>
              <div className="drama-quickstart-flow">
                <article>
                  <span>01</span>
                  <div>
                    <strong>建立故事</strong>
                    <small>梳理人物、冲突与世界观</small>
                  </div>
                </article>
                <i />
                <article>
                  <span>02</span>
                  <div>
                    <strong>拆解镜头</strong>
                    <small>统一角色、场景与视觉资产</small>
                  </div>
                </article>
                <i />
                <article>
                  <span>03</span>
                  <div>
                    <strong>合成成片</strong>
                    <small>配音、字幕、时间线与导出</small>
                  </div>
                </article>
              </div>
              <div className="drama-quickstart-examples">
                <span>没有灵感？试试这些故事种子</span>
                <div>
                  {storySeeds.map((seed) => (
                    <button
                      key={seed.label}
                      type="button"
                      onClick={() => {
                        setIdea(seed.idea);
                        setStyle(seed.style);
                        setFormat(seed.format);
                      }}
                    >
                      {seed.label}
                      <ArrowRight size={13} />
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="drama-launch-card">
              <div className="drama-launch-card-head">
                <div>
                  <span>
                    <Clapperboard size={15} /> 新建短剧
                  </span>
                  <strong>从一个故事种子开始</strong>
                </div>
                <small>设置可以随时调整</small>
              </div>
              <label>
                <span className="drama-launch-field-head">
                  <strong>你的一句话故事</strong>
                  <small>{idea.length} / 180</small>
                </span>
                <textarea
                  value={idea}
                  onChange={(event) => setIdea(event.target.value)}
                  maxLength={180}
                  placeholder="例如：一位宋朝公主发现宫廷画师偷偷记录了她的另一重身份……"
                  rows={4}
                />
              </label>
              <div className="drama-launch-options">
                <label>
                  <span>画幅</span>
                  <select
                    value={format}
                    onChange={(event) => setFormat(event.target.value)}
                  >
                    <option value="9:16">9:16 竖屏</option>
                    <option value="16:9">16:9 横屏</option>
                    <option value="1:1">1:1 方形</option>
                  </select>
                </label>
                <label>
                  <span>视觉风格</span>
                  <select
                    value={style}
                    onChange={(event) => setStyle(event.target.value)}
                  >
                    {styles.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                className="drama-launch-button"
                type="button"
                disabled={!idea.trim() || drama.saving}
                onClick={() => void createDraft()}
              >
                {drama.saving ? (
                  <Clock3 size={17} />
                ) : (
                  <WandSparkles size={17} />
                )}
                {drama.saving ? "正在创建项目…" : "创建短剧项目"}
                <ArrowRight size={16} />
              </button>
              <div className="drama-launch-meta">
                <span>
                  <CheckCircle2 size={13} /> 自动保存项目上下文
                </span>
                <span>
                  <Clock3 size={13} /> 稍后仍可调整
                </span>
              </div>
              {drama.notice && (
                <p className="drama-inline-notice">{drama.notice}</p>
              )}
            </div>
          </section>
          <section className="drama-start-roadmap">
            <div className="drama-start-roadmap-head">
              <div>
                <span className="eyebrow">制作方式</span>
                <h2>从想法到成片，每一步都可追踪</h2>
              </div>
              <p>Agent 负责起草和执行，导演负责选择、审批和锁定版本。</p>
            </div>
            <div className="drama-start-roadmap-grid">
              <article>
                <span>
                  <ScrollText size={18} />
                </span>
                <strong>剧本结构化</strong>
                <p>把灵感拆成故事圣经、分集大纲、场次与正式剧本。</p>
              </article>
              <article>
                <span>
                  <ImageIcon size={18} />
                </span>
                <strong>资产一致性</strong>
                <p>角色、服装、场景和道具版本化，多个镜头共享同一套资产。</p>
              </article>
              <article>
                <span>
                  <SplitSquareVertical size={18} />
                </span>
                <strong>逐镜生成</strong>
                <p>镜头拆解后自动选择文生视频、参考视频或首尾帧工作流。</p>
              </article>
              <article>
                <span>
                  <Clapperboard size={18} />
                </span>
                <strong>审批与合成</strong>
                <p>字幕、配音、转场和整集合成都以已锁定版本为基础。</p>
              </article>
            </div>
          </section>
        </>
      ) : (
        <div className="drama-split-layout">
          <div className="drama-main-column">
            <section className="drama-project-command">
              <div className="drama-project-identity">
                <span>
                  <Clapperboard size={18} />
                </span>
                <div>
                  <small>短剧工作台</small>
                  <strong>{project.title}</strong>
                </div>
              </div>
              <nav className="drama-phase-nav" aria-label="短剧主流程">
                {phases.map((phase, index) => {
                  const PhaseIcon = phase.icon;
                  return (
                    <button
                      key={phase.id}
                      className={activePhase.id === phase.id ? "active" : ""}
                      type="button"
                      onClick={() => selectPhase(phase)}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <PhaseIcon size={16} />
                      <div>
                        <strong>{phase.label}</strong>
                        <small>{phase.hint}</small>
                      </div>
                    </button>
                  );
                })}
              </nav>
              <div className="drama-command-actions">
                <div className="drama-view-switch">
                  <button
                    className={viewMode === "canvas" ? "active" : ""}
                    type="button"
                    onClick={() => setViewMode("canvas")}
                  >
                    <FolderKanban size={14} /> 画布
                  </button>
                  <button
                    className={viewMode === "flow" ? "active" : ""}
                    type="button"
                    onClick={() => setViewMode("flow")}
                  >
                    <SplitSquareVertical size={14} /> 制作
                  </button>
                </div>
                <span>{project.format}</span>
                <span>{project.visualStyle}</span>
                <button type="button" onClick={beginNewProject}>
                  <Plus size={14} /> 新项目
                </button>
              </div>
            </section>

            <section className="drama-live-workspace">
              <DramaScopeNavigator
                projectTitle={project.title}
                episodes={production.episodes}
                scope={canvasScope}
                selectedEpisodeId={selectedEpisodeId}
                activeStage={activeStage}
                onGlobal={selectGlobalScope}
                onEpisode={selectEpisodeScope}
                onStage={selectStageScope}
              />
              <div className="drama-live-center">
                {viewMode === "canvas" ? (
                  <DramaCanvasBoard
                    projectId={project.id}
                    projectTitle={project.title}
                    visualStyle={project.visualStyle}
                    activeStage={activeStage}
                    scope={canvasScope}
                    selectedEpisodeId={selectedEpisodeId}
                    onScopeChange={setCanvasScope}
                    onSelectEpisode={setSelectedEpisodeId}
                    onOpenStage={openCanvasStage}
                    onOpenShot={openCanvasShot}
                    onOpenAgent={openAgentForStage}
                    onScopeContextChange={setAgentContext}
                    refreshToken={workspaceVersion}
                  />
                ) : (
                  <section className="drama-workspace agent-closed">
                    <article
                      className={`drama-main-stage ${
                        productionFocusedStage ? "production-focused" : ""
                      }`}
                    >
                      <nav
                        className="drama-stage-subnav"
                        aria-label={activePhase.label}
                      >
                        {phaseStages.map((stage) => {
                          const StageIcon = stage.icon;
                          return (
                            <button
                              key={stage.id}
                              className={
                                stage.id === activeStage ? "active" : ""
                              }
                              type="button"
                              onClick={() =>
                                void drama.updateStage(project.id, stage.id)
                              }
                            >
                              <StageIcon size={14} />
                              <span>{stage.label}</span>
                              <small>
                                {String(
                                  stages.findIndex(
                                    (item) => item.id === stage.id,
                                  ) + 1,
                                ).padStart(2, "0")}
                              </small>
                            </button>
                          );
                        })}
                      </nav>
                      {!productionFocusedStage && (
                        <div className="drama-main-stage-head">
                          <div>
                            <span className="eyebrow">
                              阶段 {String(activeIndex + 1).padStart(2, "0")}
                            </span>
                            <h2>{selected.label}</h2>
                            <p>{selected.detail}</p>
                          </div>
                          <span className="drama-stage-state">
                            {activeIndex === 0
                              ? "等待 Agent 起草"
                              : "上游版本待锁定"}
                          </span>
                        </div>
                      )}

                      {!productionFocusedStage && (
                        <>
                          <div className="drama-stage-board">
                            <span className="drama-stage-board-icon">
                              <Icon size={28} />
                            </span>
                            <div>
                              <small>本阶段 Agent 任务</small>
                              <h3>{selected.output}</h3>
                              <p>{project.idea}</p>
                            </div>
                            <button
                              type="button"
                              onClick={() => openAgentForStage()}
                            >
                              <Sparkles size={15} />在 Agent 中起草
                              <small>先确认方向，再执行工具</small>
                            </button>
                          </div>

                          <div className="drama-stage-contract">
                            <div>
                              <span>交付物</span>
                              <strong>{selected.deliverable}</strong>
                            </div>
                            <div>
                              <span>下一步</span>
                              <strong>
                                {stages[Math.min(activeIndex + 1, 7)].label}
                              </strong>
                            </div>
                            <div>
                              <span>审批规则</span>
                              <strong>生成草稿 → 人工确认 → 版本锁定</strong>
                            </div>
                          </div>
                        </>
                      )}

                      {!productionFocusedStage && (
                        <DramaControlRoom
                          projectId={project.id}
                          episodeId={selectedEpisodeId}
                          stage={activeStage}
                          onOpenAgent={openAgentForStage}
                          onApproved={() => void drama.refresh()}
                          refreshToken={workspaceVersion}
                        />
                      )}

                      {documentKind ? (
                        documentKind === "script" ? (
                          <DramaScriptWorkspace
                            script={activeDocument}
                            storyBible={
                              documents.documents.find(
                                (document) => document.kind === "story_bible",
                              ) ?? null
                            }
                            draftContent={draftContent}
                            saving={documents.saving}
                            onChangeDraft={setDraftContent}
                            onSave={() => void saveStageDocument()}
                            onApprove={() =>
                              activeDocument &&
                              void documents.approve(activeDocument.id)
                            }
                            onNext={() =>
                              void drama.updateStage(project.id, "assets")
                            }
                          />
                        ) : (
                          <div className="drama-document-editor">
                            <div className="drama-document-editor-head">
                              <div>
                                <span>
                                  {activeDocument
                                    ? `v${activeDocument.version} · ${
                                        activeDocument.status === "approved"
                                          ? "已审批"
                                          : "草稿"
                                      }`
                                    : "新文档"}
                                </span>
                                <strong>{selected.deliverable}</strong>
                              </div>
                              <div>
                                {activeDocument?.status === "approved" ? (
                                  <button
                                    type="button"
                                    disabled={
                                      documents.saving || !draftContent.trim()
                                    }
                                    onClick={() =>
                                      void documents.save(
                                        documentKind,
                                        activeDocument.title,
                                        draftContent,
                                      )
                                    }
                                  >
                                    <Plus size={14} />
                                    创建新版本
                                  </button>
                                ) : (
                                  <>
                                    <button
                                      type="button"
                                      disabled={
                                        documents.saving || !draftContent.trim()
                                      }
                                      onClick={() => void saveStageDocument()}
                                    >
                                      <BookOpenText size={14} />
                                      保存草稿
                                    </button>
                                    <button
                                      type="button"
                                      disabled={
                                        !activeDocument || documents.saving
                                      }
                                      onClick={() =>
                                        activeDocument &&
                                        void documents.approve(
                                          activeDocument.id,
                                        )
                                      }
                                    >
                                      <CheckCircle2 size={14} />
                                      审批通过
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                            <textarea
                              value={draftContent}
                              readOnly={activeDocument?.status === "approved"}
                              onChange={(event) =>
                                setDraftContent(event.target.value)
                              }
                              placeholder={`开始编写${selected.label}…`}
                            />
                            <div className="drama-document-editor-foot">
                              <span>
                                {documents.loading
                                  ? "正在读取文档…"
                                  : activeDocument?.updatedAt
                                    ? `最近保存 ${activeDocument.updatedAt}`
                                    : "尚未保存"}
                              </span>
                              {documents.notice && (
                                <strong>{documents.notice}</strong>
                              )}
                            </div>
                          </div>
                        )
                      ) : activeStage === "breakdown" ? (
                        <DramaProductionBoard
                          projectId={project.id}
                          refreshToken={workspaceVersion}
                        />
                      ) : activeStage === "assets" ? (
                        <DramaAssetBoard
                          projectId={project.id}
                          refreshToken={workspaceVersion}
                          onOpenAgent={openAgentForStage}
                        />
                      ) : activeStage === "keyframes" ? (
                        <DramaKeyframeBoard
                          projectId={project.id}
                          episodeId={selectedEpisodeId}
                          initialShotId={targetShotId}
                          refreshToken={workspaceVersion}
                          onOpenAgent={openAgentForStage}
                        />
                      ) : activeStage === "clips" ? (
                        <DramaClipBoard
                          projectId={project.id}
                          aspectRatio={project.format}
                          episodeId={selectedEpisodeId}
                          initialShotId={targetShotId}
                          refreshToken={workspaceVersion}
                          onOpenAgent={openAgentForStage}
                        />
                      ) : activeStage === "timeline" ? (
                        <DramaTimelineBoard
                          projectId={project.id}
                          aspectRatio={project.format}
                          refreshToken={workspaceVersion}
                        />
                      ) : (
                        <div className="drama-empty-canvas">
                          <FolderKanban size={30} />
                          <strong>还没有 {selected.label} 内容</strong>
                          <p>
                            Agent
                            会把生成内容放在这里，并保留每一次重做、审批和版本记录。
                          </p>
                        </div>
                      )}
                      {productionFocusedStage && (
                        <details className="drama-review-drawer">
                          <summary>
                            <span>审核与制作控制</span>
                            <small>质量门、角色审核和批量运行</small>
                          </summary>
                          <DramaControlRoom
                            projectId={project.id}
                            episodeId={selectedEpisodeId}
                            stage={activeStage}
                            onOpenAgent={openAgentForStage}
                            onApproved={() => void drama.refresh()}
                            refreshToken={workspaceVersion}
                          />
                        </details>
                      )}
                    </article>
                  </section>
                )}
              </div>
            </section>
          </div>
          <div className="drama-agent-column">
            <DramaAgentPanel
              projectId={project.id}
              projectTitle={project.title}
              episodeId={agentContext.episodeId}
              stageId={activeStage}
              scope={agentContext.scope}
              scopeLabel={
                agentContext.scope === "global"
                  ? "全局项目"
                  : agentContext.scope === "episode"
                    ? `分集 · ${agentContext.episodeTitle ?? "未命名"}`
                    : `阶段 · ${selected.label}`
              }
              stageLabel={selected.label}
              threadKey={`mivo-drama-agent:${project.id}:${
                agentContext.scope === "episode"
                  ? `episode:${agentContext.episodeId ?? "current"}`
                  : agentContext.scope === "stage"
                    ? `stage:${activeStage}`
                    : "global"
              }`}
              externalPrompt={embeddedAgentPrompt}
              onPromptConsumed={() => setEmbeddedAgentPrompt("")}
              onWorkspaceChanged={() =>
                setWorkspaceVersion((version) => version + 1)
              }
            />
          </div>
        </div>
      )}
    </main>
  );
}

function documentTemplate(kind: DramaDocumentKind, idea: string) {
  if (kind === "brief") {
    return [
      "一句话故事",
      idea || "待填写",
      "",
      "目标观众",
      "待填写",
      "",
      "视觉方向",
      "待填写",
      "",
      "制作约束",
      "单集时长、画幅、禁用元素和审核要求。",
    ].join("\n");
  }
  if (kind === "story_bible") {
    return [
      "核心角色",
      "- 姓名：",
      "- 年龄与身份：",
      "- 外貌与服装：",
      "- 性格与目标：",
      "",
      "主要场景",
      "- 地点：",
      "- 时间与氛围：",
      "",
      "关键道具",
      "- 名称：",
      "- 剧情作用：",
      "",
      "连续性规则",
      "- 不得改变的设定：",
    ].join("\n");
  }
  return [
    "第 1 集",
    "",
    "场次 1｜内景｜地点｜日/夜",
    "",
    "动作：",
    "",
    "角色：",
    "对白：",
  ].join("\n");
}
