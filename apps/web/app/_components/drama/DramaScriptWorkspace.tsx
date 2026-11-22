"use client";

import {
  BookOpenText,
  CheckCircle2,
  ChevronRight,
  FilePenLine,
  ListTree,
  LockKeyhole,
  Save,
  ScrollText,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DramaDocument } from "../../_features/drama/types";

type DramaScriptWorkspaceProps = {
  script: DramaDocument | null;
  storyBible: DramaDocument | null;
  draftContent: string;
  saving: boolean;
  onChangeDraft: (value: string) => void;
  onSave: () => void;
  onApprove: () => void;
  onNext: () => void;
};

type ScriptTab = "setting" | "outline" | "body";

export function DramaScriptWorkspace({
  script,
  storyBible,
  draftContent,
  saving,
  onChangeDraft,
  onSave,
  onApprove,
  onNext,
}: DramaScriptWorkspaceProps) {
  const [tab, setTab] = useState<ScriptTab>("body");
  const [editing, setEditing] = useState(false);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(
    null,
  );
  const episodes = useMemo(
    () => extractEpisodes(draftContent),
    [draftContent],
  );
  const selectedEpisode =
    episodes.find((episode) => episode.id === selectedEpisodeId) ??
    episodes[0];
  const approved = script?.status === "approved";
  const content = script?.content || draftContent;
  const charCount = content.replace(/\s/g, "").length;
  const estimatedSeconds = Math.max(30, Math.round(charCount / 4.2));

  return (
    <section className="drama-script-workspace">
      <header className="drama-script-head">
        <div>
          <span>剧本</span>
          <em>单集建议 3–5 分钟</em>
          <em className={approved ? "approved" : ""}>
            {approved ? "已审批" : "待审批"}
          </em>
          <em>第 1 集</em>
          <em>约 {formatDuration(estimatedSeconds)}</em>
          <em>{charCount} 字</em>
          {approved && <em><LockKeyhole size={11} /> 已锁定</em>}
        </div>
        <div>
          <button
            type="button"
            disabled={approved || saving}
            onClick={() => setEditing((value) => !value)}
          >
            <FilePenLine size={13} />
            {editing ? "阅读模式" : "编辑正文"}
          </button>
        </div>
      </header>

      <nav className="drama-script-tabs" aria-label="剧本内容">
        <button
          className={tab === "setting" ? "active" : ""}
          type="button"
          onClick={() => setTab("setting")}
        >
          <BookOpenText size={14} /> 故事设定
        </button>
        <button
          className={tab === "outline" ? "active" : ""}
          type="button"
          onClick={() => setTab("outline")}
        >
          <ListTree size={14} /> 分集大纲
        </button>
        <button
          className={tab === "body" ? "active" : ""}
          type="button"
          onClick={() => setTab("body")}
        >
          <ScrollText size={14} /> 剧本正文
        </button>
      </nav>

      <div className="drama-script-layout">
        <aside className="drama-script-directory">
          <span>剧本目录</span>
          {episodes.map((episode) => (
            <button
              key={episode.id}
              className={
                episode.id === selectedEpisode?.id ? "active" : ""
              }
              type="button"
              onClick={() => setSelectedEpisodeId(episode.id)}
            >
              第 {episode.number} 集
            </button>
          ))}
        </aside>

        <article className="drama-script-paper">
          {tab === "setting" ? (
            <DocumentPane
              title="故事设定"
              content={
                storyBible?.content
                || "尚未创建故事圣经。请先与 Agent 确认角色、场景、道具和连续性规则。"
              }
            />
          ) : tab === "outline" ? (
            <OutlinePane content={content} episodes={episodes} />
          ) : editing && !approved ? (
            <div className="drama-script-editor">
              <textarea
                value={draftContent}
                onChange={(event) => onChangeDraft(event.target.value)}
              />
              <footer>
                <span>{draftContent.length} 字</span>
                <button
                  type="button"
                  disabled={saving || !draftContent.trim()}
                  onClick={onSave}
                >
                  <Save size={14} /> 保存草稿
                </button>
              </footer>
            </div>
          ) : (
            <div className="drama-script-reading">
              <header>
                <span>第 1 集</span>
                <h3>{selectedEpisode?.title || "当前剧本"}</h3>
              </header>
              <div className="drama-script-markdown">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {content || "尚未生成剧本正文。"}
                </Markdown>
              </div>
            </div>
          )}
        </article>
      </div>

      <footer className="drama-script-next">
        <div>
          <Sparkles size={15} />
          <span>
            {approved
              ? "剧本已确认，可以继续拆解每集时间、人物、场景和镜头。"
              : "剧本完成并审批后，再进入逐集拆解和资产制作。"}
          </span>
        </div>
        {!approved ? (
          <button
            className="primary"
            type="button"
            disabled={!script || saving}
            onClick={onApprove}
          >
            <CheckCircle2 size={14} /> 确认当前剧本
          </button>
        ) : (
          <button className="primary" type="button" onClick={onNext}>
            开始分集与镜头拆解 <ChevronRight size={14} />
          </button>
        )}
      </footer>
    </section>
  );
}

function DocumentPane({
  title,
  content,
}: {
  title: string;
  content: string;
}) {
  return (
    <div className="drama-script-reading">
      <header>
        <span>项目设定</span>
        <h3>{title}</h3>
      </header>
      <div className="drama-script-markdown">
        <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
      </div>
    </div>
  );
}

function OutlinePane({
  content,
  episodes,
}: {
  content: string;
  episodes: ReturnType<typeof extractEpisodes>;
}) {
  const scenes = extractScenes(content);
  return (
    <div className="drama-script-outline">
      <header>
        <span>分集大纲</span>
        <h3>{episodes.length} 集 · {scenes.length} 场</h3>
      </header>
      {episodes.map((episode) => (
        <article key={episode.id}>
          <strong>第 {episode.number} 集 · {episode.title}</strong>
          <p>{episode.summary || "本集暂无独立大纲摘要"}</p>
        </article>
      ))}
      <div className="drama-script-scene-list">
        {scenes.map((scene, index) => (
          <span key={`${scene}-${index}`}>
            {String(index + 1).padStart(2, "0")} {scene}
          </span>
        ))}
      </div>
    </div>
  );
}

function extractEpisodes(content: string) {
  const matches = Array.from(
    content.matchAll(
      /(?:^|\n)(?:#{1,4}\s*)?第\s*(\d+)\s*集[：:\s·-]*(.*)/g,
    ),
  );
  if (!matches.length) {
    return [{
      id: "episode-1",
      number: 1,
      title: "未命名分集",
      summary: "",
    }];
  }
  return matches.map((match, index) => {
    const start = match.index ?? 0;
    const end = matches[index + 1]?.index ?? content.length;
    const section = content.slice(start, end).trim();
    return {
      id: `episode-${match[1]}`,
      number: Number(match[1]),
      title: match[2]?.trim() || "未命名分集",
      summary: section.split("\n").slice(1, 4).join(" ").slice(0, 120),
    };
  });
}

function extractScenes(content: string) {
  return Array.from(
    content.matchAll(
      /(?:^|\n)\s*(?:#{1,4}\s*)?((?:场|场景)\s*\d+(?:-\d+)?[^\n]*)/g,
    ),
  )
    .map((match) => match[1].trim())
    .slice(0, 80);
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes} 分 ${String(rest).padStart(2, "0")} 秒`;
}
