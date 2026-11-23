"use client";

import {
  BookOpenText,
  Clapperboard,
  FolderKanban,
  Image as ImageIcon,
  ListTree,
  ScrollText,
  Sparkles,
} from "lucide-react";
import type { DramaEpisode } from "../../_features/drama/types";
import { dramaStages } from "../../_features/drama/productionStages";

type DramaScope = "global" | "episode" | "stage";

type DramaScopeNavigatorProps = {
  projectTitle: string;
  episodes: DramaEpisode[];
  scope: DramaScope;
  selectedEpisodeId: string | null;
  activeStage: string;
  onGlobal: () => void;
  onEpisode: (episodeId: string) => void;
  onStage: (stageId: string) => void;
};

export function DramaScopeNavigator({
  projectTitle,
  episodes,
  scope,
  selectedEpisodeId,
  activeStage,
  onGlobal,
  onEpisode,
  onStage,
}: DramaScopeNavigatorProps) {
  return (
    <aside className="drama-scope-navigator">
      <header>
        <span><Clapperboard size={16} /></span>
        <div>
          <strong>制作范围</strong>
          <small title={projectTitle}>{projectTitle}</small>
        </div>
      </header>

      <section className="drama-scope-nav-section">
        <button
          className={scope === "global" ? "active" : ""}
          type="button"
          onClick={onGlobal}
        >
          <Sparkles size={14} />
          <span>
            <strong>全局总览</strong>
            <small>跨阶段关系与整体进度</small>
          </span>
        </button>
      </section>

      <section className="drama-scope-nav-section">
        <div className="drama-scope-nav-label">
          <span>分集</span>
          <small>{episodes.length}</small>
        </div>
        <div className="drama-scope-episode-list">
          {episodes.map((episode) => {
            const shots = episode.scenes.flatMap((scene) => scene.shots);
            return (
              <button
                key={episode.id}
                className={
                  scope === "episode"
                  && selectedEpisodeId === episode.id
                    ? "active"
                    : ""
                }
                type="button"
                onClick={() => onEpisode(episode.id)}
              >
                <span>{String(episode.episodeNumber).padStart(2, "0")}</span>
                <div>
                  <strong>{episode.title}</strong>
                  <small>
                    {episode.scenes.length} 场 · {shots.length} 镜 ·
                    {" "}
                    {shots.filter((shot) => shot.videoAssetId).length} 视频
                  </small>
                </div>
              </button>
            );
          })}
          {!episodes.length && (
            <p>完成剧本后创建第一集</p>
          )}
        </div>
      </section>

      <section className="drama-scope-nav-section drama-scope-stage-list">
        <div className="drama-scope-nav-label">
          <span>制作阶段</span>
          <small>{activeStage}</small>
        </div>
        {dramaStages.map((stage) => {
          const Icon = stageIcon(stage.id);
          return (
            <button
              key={stage.id}
              className={
                scope === "stage" && activeStage === stage.id
                  ? "active"
                  : ""
              }
              type="button"
              onClick={() => onStage(stage.id)}
            >
              <Icon size={14} />
              <span>
                <strong>{stage.label}</strong>
                <small>{stage.deliverable}</small>
              </span>
            </button>
          );
        })}
      </section>
    </aside>
  );
}

function stageIcon(stageId: string) {
  return {
    brief: Sparkles,
    bible: BookOpenText,
    script: ScrollText,
    breakdown: ListTree,
    assets: ImageIcon,
    keyframes: FolderKanban,
    clips: Clapperboard,
    timeline: Clapperboard,
  }[stageId] ?? ScrollText;
}
