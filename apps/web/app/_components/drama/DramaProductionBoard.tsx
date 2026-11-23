"use client";

import {
  CheckCircle2,
  Clapperboard,
  FolderPlus,
  ListVideo,
  Plus,
  Save,
} from "lucide-react";
import { useEffect, useState } from "react";
import type {
  DramaEpisode,
  DramaEpisodePlan,
} from "../../_features/drama/types";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";

type DramaProductionBoardProps = {
  projectId: string;
  refreshToken?: number;
};

export function DramaProductionBoard({
  projectId,
  refreshToken = 0,
}: DramaProductionBoardProps) {
  const production = useDramaProduction(projectId);
  const [activeEpisodeId, setActiveEpisodeId] = useState<string | null>(null);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [sceneHeading, setSceneHeading] = useState("");
  const [shotTitle, setShotTitle] = useState("");
  const [shotDescription, setShotDescription] = useState("");
  const [shotDuration, setShotDuration] = useState(5);

  useEffect(() => {
    if (
      activeEpisodeId &&
      production.episodes.some((episode) => episode.id === activeEpisodeId)
    ) {
      return;
    }
    setActiveEpisodeId(production.episodes[0]?.id ?? null);
  }, [activeEpisodeId, production.episodes]);

  const activeEpisode =
    production.episodes.find((episode) => episode.id === activeEpisodeId) ??
    null;

  useEffect(() => {
    if (
      activeSceneId &&
      activeEpisode?.scenes.some((scene) => scene.id === activeSceneId)
    ) {
      return;
    }
    setActiveSceneId(activeEpisode?.scenes[0]?.id ?? null);
  }, [activeEpisode, activeSceneId]);

  useEffect(() => {
    if (refreshToken) void production.refresh();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const activeScene =
    activeEpisode?.scenes.find((scene) => scene.id === activeSceneId) ?? null;
  const sceneCount = production.episodes.reduce(
    (count, episode) => count + episode.scenes.length,
    0,
  );
  const shotCount = production.episodes.reduce(
    (count, episode) =>
      count +
      episode.scenes.reduce(
        (sceneTotal, scene) => sceneTotal + scene.shots.length,
        0,
      ),
    0,
  );

  async function addScene() {
    if (!activeEpisode || !sceneHeading.trim()) return;
    const scene = await production.addScene(
      activeEpisode.id,
      sceneHeading.trim(),
    );
    if (scene) {
      setSceneHeading("");
      setActiveSceneId(scene.id);
    }
  }

  async function addShot() {
    if (!activeScene || !shotTitle.trim()) return;
    const shot = await production.addShot(activeScene.id, {
      title: shotTitle.trim(),
      description: shotDescription.trim(),
      durationSeconds: shotDuration,
    });
    if (shot) {
      setShotTitle("");
      setShotDescription("");
    }
  }

  return (
    <section className="drama-production-board">
      <header className="drama-production-head">
        <div>
          <span>制作图谱</span>
          <strong>分集 / 场次 / 镜头</strong>
        </div>
        <div className="drama-production-summary">
          <span>{production.episodes.length} 集</span>
          <span>{sceneCount} 场</span>
          <span>{shotCount} 镜</span>
        </div>
      </header>

      {production.episodes.length === 0 ? (
        <div className="drama-production-empty">
          <ListVideo size={30} />
          <strong>还没有分集</strong>
          <p>先把已审批剧本拆成第 1 集，再继续添加场次和镜头。</p>
          <button
            type="button"
            disabled={production.saving}
            onClick={() => void production.addEpisode("第 1 集")}
          >
            <FolderPlus size={15} /> 创建第 1 集
          </button>
        </div>
      ) : (
        <>
        {activeEpisode && (
          <EpisodePlanEditor
            key={activeEpisode.id}
            episode={activeEpisode}
            saving={production.saving}
            onSave={production.updateEpisodePlan}
          />
        )}
        <div className="drama-production-columns">
          <section className="drama-episode-column">
            <div className="drama-production-column-head">
              <span>分集</span>
              <button
                type="button"
                title="新建分集"
                disabled={production.saving}
                onClick={() =>
                  void production.addEpisode(
                    `第 ${production.episodes.length + 1} 集`,
                  )
                }
              >
                <Plus size={13} />
              </button>
            </div>
            {production.episodes.map((episode) => (
              <button
                key={episode.id}
                className={episode.id === activeEpisodeId ? "active" : ""}
                type="button"
                onClick={() => setActiveEpisodeId(episode.id)}
              >
                <span>{String(episode.episodeNumber).padStart(2, "0")}</span>
                <div>
                  <strong>{episode.title}</strong>
                  <small>{episode.scenes.length} 场</small>
                </div>
              </button>
            ))}
          </section>

          <section className="drama-scene-column">
            <div className="drama-production-column-head">
              <span>场次</span>
              <small>{activeEpisode?.title}</small>
            </div>
            <div className="drama-inline-create">
              <input
                value={sceneHeading}
                onChange={(event) => setSceneHeading(event.target.value)}
                placeholder="内景｜公主寝宫｜夜"
              />
              <button
                type="button"
                disabled={!sceneHeading.trim() || production.saving}
                onClick={() => void addScene()}
              >
                <Plus size={13} /> 添加场次
              </button>
            </div>
            <div className="drama-scene-list">
              {activeEpisode?.scenes.map((scene) => (
                <button
                  key={scene.id}
                  className={scene.id === activeSceneId ? "active" : ""}
                  type="button"
                  onClick={() => setActiveSceneId(scene.id)}
                >
                  <span>场 {scene.sceneNumber}</span>
                  <strong>{scene.heading}</strong>
                  <small>{scene.shots.length} 个镜头</small>
                </button>
              ))}
              {!activeEpisode?.scenes.length && (
                <p className="drama-column-empty">先添加一个场次</p>
              )}
            </div>
          </section>

          <section className="drama-shot-column">
            <div className="drama-production-column-head">
              <span>镜头</span>
              <small>{activeScene?.heading ?? "请选择场次"}</small>
            </div>
            {activeScene && (
              <>
                <div className="drama-shot-create">
                  <input
                    value={shotTitle}
                    onChange={(event) => setShotTitle(event.target.value)}
                    placeholder="镜头标题，例如：铜镜前的发现"
                  />
                  <textarea
                    value={shotDescription}
                    onChange={(event) =>
                      setShotDescription(event.target.value)
                    }
                    placeholder="画面、动作、镜头语言与对白…"
                  />
                  <div>
                    <label>
                      <span>时长</span>
                      <input
                        type="number"
                        min={0.1}
                        max={60}
                        step={0.1}
                        value={shotDuration}
                        onChange={(event) =>
                          setShotDuration(Number(event.target.value))
                        }
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!shotTitle.trim() || production.saving}
                      onClick={() => void addShot()}
                    >
                      <Clapperboard size={14} /> 添加镜头
                    </button>
                  </div>
                </div>
                <div className="drama-shot-list">
                  {activeScene.shots.map((shot) => (
                    <article key={shot.id}>
                      <div className="drama-shot-head">
                        <span>镜头 {shot.shotNumber}</span>
                        <strong>{shot.title}</strong>
                        <small>{shot.durationSeconds}s</small>
                      </div>
                      <p>{shot.description || "尚未填写画面描述"}</p>
                      <div className="drama-shot-status">
                        <span className={shot.status}>
                          {shotStatusLabel(shot.status)}
                        </span>
                        {shot.status === "planned" && (
                          <button
                            type="button"
                            onClick={() =>
                              void production.setShotStatus(
                                shot.id,
                                "keyframe_ready",
                              )
                            }
                          >
                            <CheckCircle2 size={13} />
                            标记关键帧就绪
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                  {!activeScene.shots.length && (
                    <p className="drama-column-empty">还没有镜头</p>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
        </>
      )}

      <footer className="drama-production-foot">
        <span>
          {production.loading
            ? "正在读取制作图谱…"
            : "镜头状态将成为关键帧和视频任务的依赖。"}
        </span>
        {production.notice && <strong>{production.notice}</strong>}
      </footer>
    </section>
  );
}

function EpisodePlanEditor({
  episode,
  saving,
  onSave,
}: {
  episode: DramaEpisode;
  saving: boolean;
  onSave: (
    episodeId: string,
    plan: DramaEpisodePlan,
  ) => Promise<DramaEpisode | null>;
}) {
  const [timeScope, setTimeScope] = useState(episode.plan?.timeScope ?? "");
  const [locations, setLocations] = useState(
    episode.plan?.locations.join("\n") ?? "",
  );
  const [interiorExterior, setInteriorExterior] = useState(
    episode.plan?.interiorExterior.join("\n") ?? "",
  );
  const [characters, setCharacters] = useState(
    episode.plan?.characters.join("\n") ?? "",
  );
  const [scenes, setScenes] = useState(
    episode.plan?.scenes.join("\n") ?? "",
  );
  const [storyBeats, setStoryBeats] = useState(
    episode.plan?.storyBeats.join("\n") ?? "",
  );
  const [visualRequirements, setVisualRequirements] = useState(
    episode.plan?.visualRequirements.join("\n") ?? "",
  );
  const [dialogueRequirements, setDialogueRequirements] = useState(
    episode.plan?.dialogueRequirements.join("\n") ?? "",
  );
  const [continuityRisks, setContinuityRisks] = useState(
    episode.plan?.continuityRisks.join("\n") ?? "",
  );

  async function save() {
    await onSave(episode.id, {
      timeScope: timeScope.trim(),
      locations: lines(locations),
      interiorExterior: lines(interiorExterior),
      characters: lines(characters),
      scenes: lines(scenes),
      storyBeats: lines(storyBeats),
      visualRequirements: lines(visualRequirements),
      dialogueRequirements: lines(dialogueRequirements),
      continuityRisks: lines(continuityRisks),
      sceneContracts: episode.plan?.sceneContracts ?? [],
    });
  }

  return (
    <section className="drama-episode-plan">
      <header>
        <div>
          <span>逐集制作蓝图</span>
          <strong>
            第 {episode.episodeNumber} 集 · {episode.title}
          </strong>
        </div>
        <button type="button" disabled={saving} onClick={() => void save()}>
          <Save size={14} /> 保存分集计划
        </button>
      </header>
      <div className="drama-episode-plan-grid">
        <label>
          <span>时间范围</span>
          <input
            value={timeScope}
            onChange={(event) => setTimeScope(event.target.value)}
            placeholder="例如：同一夜，从戌时到次日卯时"
          />
        </label>
        <ListField
          label="地点"
          value={locations}
          onChange={setLocations}
          placeholder="每行一个地点"
        />
        <ListField
          label="内外景"
          value={interiorExterior}
          onChange={setInteriorExterior}
          placeholder={"内景｜公主寝宫\n外景｜宫墙"}
        />
        <ListField
          label="人物"
          value={characters}
          onChange={setCharacters}
          placeholder="每行一个出场人物"
        />
        <ListField
          label="场景与故事节拍"
          value={scenes}
          onChange={setScenes}
          placeholder={"1. 镜中发现画像\n2. 画师闯入"}
        />
        <ListField
          label="故事推进"
          value={storyBeats}
          onChange={setStoryBeats}
          placeholder={"发现秘密 → 追查身份 → 留钩子"}
        />
        <ListField
          label="画面检查"
          value={visualRequirements}
          onChange={setVisualRequirements}
          placeholder={"铜镜反光方向一致\n公主服装保持月白"}
        />
        <ListField
          label="对白与声音"
          value={dialogueRequirements}
          onChange={setDialogueRequirements}
          placeholder={"每句对白标注说话人\n保留环境竹叶声"}
        />
        <ListField
          label="连续性风险"
          value={continuityRisks}
          onChange={setContinuityRisks}
          placeholder={"画像出现时间需与前集一致"}
        />
      </div>
    </section>
  );
}

function ListField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label>
      <span>{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={2}
      />
    </label>
  );
}

function lines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function shotStatusLabel(status: string) {
  return {
    planned: "待制作",
    keyframe_ready: "关键帧就绪",
    clip_ready: "视频就绪",
    approved: "已通过",
  }[status] ?? status;
}
