"use client";

import {
  CheckCircle2,
  ClipboardList,
  Loader2,
  Play,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { useDirectorWorkflow } from "../hooks/use-director-workflow";

type Props = {
  sessionId: string | null;
  onPromptReady: (prompt: string, projectId: string) => Promise<void>;
};

const DEFAULT_IDEA =
  "写一篇关于一只猫的小说。它想完成一次属于自己的冒险，故事要连续、有反转、有温暖结尾。";

export function DirectorWorkflowPanel({ sessionId, onPromptReady }: Props) {
  const [idea, setIdea] = useState(DEFAULT_IDEA);
  const [chapterCount, setChapterCount] = useState(6);
  const [targetWords, setTargetWords] = useState(6000);
  const { project, notice, loading, createNovelProject } =
    useDirectorWorkflow(onPromptReady);

  function createProject() {
    void createNovelProject({
      idea,
      chapterCount,
      targetWords,
      sessionId,
    });
  }

  return (
    <section className="director-panel" aria-label="小说工作流">
      <div className="director-copy">
        <span className="director-eyebrow">
          <Sparkles size={15} />
          小说 Agent 工作流
        </span>
        <h2>先把创意变成一篇可读的小说</h2>
        <p>
          创建后会立即生成项目、工作空间、小说设定集、章节大纲和一版
          Markdown 正文草稿，并聚合到 exports/novel-project.md。
        </p>
      </div>
      <div className="director-form">
        <textarea
          value={idea}
          onChange={(event) => setIdea(event.target.value)}
          aria-label="小说创意"
        />
        <div className="director-controls">
          <label>
            <span>章节数</span>
            <input
              type="number"
              min={1}
              max={200}
              value={chapterCount}
              onChange={(event) => setChapterCount(Number(event.target.value))}
            />
          </label>
          <label>
            <span>目标字数</span>
            <input
              type="number"
              min={500}
              max={300000}
              step={500}
              value={targetWords}
              onChange={(event) => setTargetWords(Number(event.target.value))}
            />
          </label>
          <button type="button" onClick={createProject} disabled={loading}>
            {loading ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
            生成草稿
          </button>
        </div>
        {notice && <p className="director-notice">{notice}</p>}
      </div>
      {project?.workflow && (
        <div className="workflow-preview">
          <div className="workflow-head">
            <ClipboardList size={17} />
            <div>
              <strong>{project.title}</strong>
              <small>{project.workspacePath}</small>
            </div>
          </div>
          <ol>
            {project.workflow.steps.map((step) => (
              <li key={step.id}>
                <CheckCircle2 size={15} />
                <span>
                  <strong>{step.title}</strong>
                  <small>{step.summary}</small>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
