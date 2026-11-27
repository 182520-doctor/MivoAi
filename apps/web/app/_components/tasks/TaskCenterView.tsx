"use client";

import {
  CheckCircle2,
  CircleDot,
  Clock3,
  ListTodo,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { mediaAssetUrl } from "../../_features/media/api";
import {
  loadTaskCenter,
  retryMediaTask,
  retryMediaTasks,
} from "../../_features/tasks/api";
import type {
  TaskCenterItem,
  TaskCenterResponse,
} from "../../_features/tasks/types";

type TaskFilter = "all" | "active" | "succeeded" | "failed";

const filters: Array<{
  id: TaskFilter;
  label: string;
  icon: typeof ListTodo;
}> = [
  { id: "all", label: "全部", icon: ListTodo },
  { id: "active", label: "排队 / 执行中", icon: Clock3 },
  { id: "succeeded", label: "已完成", icon: CheckCircle2 },
  { id: "failed", label: "失败", icon: TriangleAlert },
];

export function TaskCenterView() {
  const [data, setData] = useState<TaskCenterResponse>({
    tasks: [],
    summary: {},
  });
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [retryingIds, setRetryingIds] = useState<string[]>([]);
  const [batchRetrying, setBatchRetrying] = useState(false);
  const [error, setError] = useState("");

  async function refresh(silent = false) {
    if (!silent) setLoading(true);
    setError("");
    try {
      setData(await loadTaskCenter());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(true), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const mediaTasks = useMemo(
    () => data.tasks.filter((task) => task.taskType !== "text"),
    [data.tasks],
  );

  const counts = useMemo(() => {
    const tasks = mediaTasks;
    return {
      all: tasks.length,
      active: tasks.filter((task) =>
        ["pending", "queued", "running"].includes(task.status),
      ).length,
      succeeded: tasks.filter((task) =>
        ["succeeded", "completed"].includes(task.status),
      ).length,
      failed: tasks.filter((task) =>
        ["failed", "error", "canceled"].includes(task.status),
      ).length,
    };
  }, [mediaTasks]);

  const visibleTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return mediaTasks.filter((task) => {
      const statusMatches =
        filter === "all" ||
        (filter === "active" &&
          ["pending", "queued", "running"].includes(task.status)) ||
        (filter === "succeeded" &&
          ["succeeded", "completed"].includes(task.status)) ||
        (filter === "failed" &&
          ["failed", "error", "canceled"].includes(task.status));
      if (!statusMatches) return false;
      if (!keyword) return true;
      const searchable = [
        task.id,
        task.prompt,
        task.providerName,
        task.modelName,
        task.taskType,
      ]
        .join(" ")
        .toLowerCase();
      return searchable.includes(keyword);
    });
  }, [mediaTasks, filter, query]);

  async function retryTask(taskId: string) {
    setRetryingIds((items) => [...items, taskId]);
    setError("");
    try {
      await retryMediaTask(taskId);
      await refresh(true);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setRetryingIds((items) => items.filter((id) => id !== taskId));
    }
  }

  async function retryVisibleFailures() {
    const failedIds = visibleTasks
      .filter((task) => ["failed", "error", "canceled"].includes(task.status))
      .slice(0, 20)
      .map((task) => task.id);
    if (!failedIds.length) return;
    if (
      !window.confirm(
        `将重试当前筛选中的 ${failedIds.length} 个失败任务，` +
          "可能重新占用模型或 GPU，是否继续？",
      )
    ) {
      return;
    }
    setBatchRetrying(true);
    setError("");
    try {
      const result = await retryMediaTasks(failedIds);
      if (result.failures.length) {
        setError(
          `${result.tasks.length} 个任务已重新提交，` +
            `${result.failures.length} 个失败：` +
            result.failures[0].error,
        );
      }
      await refresh(true);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBatchRetrying(false);
    }
  }

  return (
    <main className="workbench-page task-center-page">
      <header className="page-heading compact workbench-page-heading">
        <div>
          <span className="eyebrow">生产运行</span>
          <h1>任务中心</h1>
          <p>
            跟踪排队、执行与失败任务，查看真实模型和结果素材；失败任务可以保留原参数重新提交。
          </p>
        </div>
        <div className="heading-status">
          <span className="status-chip">{counts.all} 个媒体任务</span>
          <span
            className={`status-chip ${counts.active ? "warning" : "ready"}`}
          >
            {counts.active ? `${counts.active} 个执行中` : "队列空闲"}
          </span>
        </div>
      </header>
      <section className="task-filter-bar task-center-filters">
        <div>
          {filters.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={filter === id ? "active" : ""}
              onClick={() => setFilter(id)}
            >
              <Icon size={15} />
              {label}
              <span>{counts[id]}</span>
            </button>
          ))}
        </div>
        <label className="task-center-search">
          <Search size={16} />
          <input
            aria-label="搜索任务"
            placeholder="搜索提示词、模型或任务 ID"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="workspace-toolbar-actions">
          <span className="status-chip ready">
            {counts.active} 个任务执行中
          </span>
          <button
            className="compact-action"
            type="button"
            onClick={() => void refresh()}
          >
            <RefreshCw className={loading ? "spin" : ""} size={15} />
            刷新
          </button>
          <button
            className="compact-action"
            type="button"
            disabled={batchRetrying || counts.failed === 0}
            onClick={() => void retryVisibleFailures()}
          >
            <RotateCcw className={batchRetrying ? "spin" : ""} size={15} />
            批量重试失败
          </button>
        </div>
      </section>

      {error && (
        <div className="generation-error">
          <TriangleAlert size={16} />
          <span>{error}</span>
        </div>
      )}

      <section className="task-center-list">
        {visibleTasks.map((task) => (
          <TaskRow
            task={task}
            key={task.id}
            retrying={retryingIds.includes(task.id)}
            onRetry={() => void retryTask(task.id)}
          />
        ))}
        {!loading && visibleTasks.length === 0 && (
          <div className="empty-library task-empty-page">
            <span className="empty-library-icon">
              <CircleDot size={30} />
            </span>
            <h2>当前筛选没有任务</h2>
            <p>任务提交后会持久化保存在这里，刷新浏览器也不会消失。</p>
          </div>
        )}
        {loading && (
          <div className="task-loading">
            <LoaderCircle className="spin" size={20} />
            正在读取任务数据
          </div>
        )}
      </section>
    </main>
  );
}

function TaskRow({
  task,
  retrying,
  onRetry,
}: {
  task: TaskCenterItem;
  retrying: boolean;
  onRetry: () => void;
}) {
  const status = taskStatus(task.status);
  return (
    <article className="task-center-row">
      <div className={`task-status-mark ${status.className}`}>
        {status.icon}
      </div>
      <div className="task-row-main">
        <div className="task-row-head">
          <strong>{taskTypeLabel(task.taskType)}</strong>
          <span className={`task-status-text ${status.className}`}>
            {status.label}
          </span>
        </div>
        <p>{displayTaskPrompt(task.prompt)}</p>
        <div className="task-row-meta">
          <span>{task.providerName}</span>
          <span>{task.modelName}</span>
          <span>{formatTime(task.createdAt)}</span>
          <code>{task.id.slice(0, 8)}</code>
        </div>
        {task.origin?.kind === "drama_production_run" && (
          <div className="task-origin">
            <span>短剧</span>
            <code>{task.origin.projectId?.slice(0, 8)}</code>
            <span>分集</span>
            <code>{task.origin.episodeId?.slice(0, 8)}</code>
            <span>运行</span>
            <code>{task.origin.productionRunId?.slice(0, 8)}</code>
            <span>{task.origin.targetType === "shot" ? "镜头" : "资产"}</span>
            <code>{task.origin.targetId?.slice(0, 8)}</code>
            <span>{task.origin.slot}</span>
          </div>
        )}
        {task.progress != null &&
          ["pending", "queued", "running"].includes(task.status) && (
            <div className="task-progress">
              <span style={{ width: `${Math.max(task.progress, 2)}%` }} />
              <strong>{task.progress}%</strong>
            </div>
          )}
        {task.errorMessage && (
          <p className="task-row-error">{task.errorMessage}</p>
        )}
      </div>
      {task.resultAssetIds.length > 0 && (
        <div className="task-result-preview">
          {task.resultAssetIds
            .slice(0, 3)
            .map((assetId) =>
              task.taskType === "video_generation" ? (
                <video key={assetId} src={mediaAssetUrl(assetId)} muted />
              ) : (
                <img
                  key={assetId}
                  src={mediaAssetUrl(assetId)}
                  alt="任务结果"
                />
              ),
            )}
        </div>
      )}
      {["failed", "error", "canceled"].includes(task.status) &&
        task.taskType !== "text" && (
          <button
            className="task-retry-button"
            type="button"
            disabled={retrying}
            onClick={onRetry}
          >
            {retrying ? (
              <LoaderCircle className="spin" size={14} />
            ) : (
              <RotateCcw size={14} />
            )}
            {retrying ? "提交中" : "重试任务"}
          </button>
        )}
    </article>
  );
}

function taskStatus(status: string) {
  if (["pending", "queued"].includes(status)) {
    return {
      label: "排队中",
      className: "queued",
      icon: <Clock3 size={17} />,
    };
  }
  if (status === "running") {
    return {
      label: "执行中",
      className: "running",
      icon: <Play size={17} />,
    };
  }
  if (["succeeded", "completed"].includes(status)) {
    return {
      label: "已完成",
      className: "succeeded",
      icon: <CheckCircle2 size={17} />,
    };
  }
  return {
    label: status === "canceled" ? "已取消" : "失败",
    className: "failed",
    icon: <TriangleAlert size={17} />,
  };
}

function taskTypeLabel(taskType: string) {
  return (
    {
      image_generation: "图片生成",
      image_processing: "图片处理",
      video_generation: "视频生成",
      video_processing: "视频处理",
      audio_processing: "音频处理",
      transcription: "语音转字幕",
      text: "Agent 对话",
    }[taskType] ?? taskType
  );
}

function displayTaskPrompt(prompt: string) {
  if (!prompt) return "无提示词";
  if (prompt.startsWith("【短剧工作台上下文】")) {
    const marker = "用户消息：";
    const index = prompt.indexOf(marker);
    if (index >= 0) {
      return prompt.slice(index + marker.length).trim() || "短剧 Agent 任务";
    }
  }
  return prompt;
}

function formatTime(value: string) {
  const date = new Date(value.replace(" ", "T") + "Z");
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}
