"use client";

import {
  Bot,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  cancelDramaProductionRun,
  loadDramaProductionRuns,
  retryDramaProductionRun,
  startDramaProductionRun,
} from "../../_features/drama/api";
import type {
  DramaProductionRun,
  DramaProductionRunItem,
} from "../../_features/drama/types";

type DramaProductionRunPanelProps = {
  projectId: string;
  stage: string;
  episodeId?: string | null;
  refreshToken?: number;
  onOpenAgent: () => void;
};

export function DramaProductionRunPanel({
  projectId,
  stage,
  episodeId,
  refreshToken = 0,
  onOpenAgent,
}: DramaProductionRunPanelProps) {
  const [runs, setRuns] = useState<DramaProductionRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyRunId, setBusyRunId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showCanceled, setShowCanceled] = useState(false);
  const canceledCount = runs.filter((run) => run.status === "canceled").length;
  const visibleRuns = showCanceled
    ? runs
    : runs.filter((run) => run.status !== "canceled");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = await loadDramaProductionRuns(
        projectId,
        episodeId,
        30,
      );
      setRuns(items.filter((run) => run.stage === stage));
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setLoading(false);
    }
  }, [episodeId, projectId, stage]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshToken]);

  useEffect(() => {
    if (!runs.some((run) => ["queued", "running"].includes(run.status))) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [refresh, runs]);

  async function start(run: DramaProductionRun) {
    if (
      !window.confirm(
        `将启动“${run.name}”的 ${run.items.length} 个制作任务，`
        + `并行数 ${run.maxParallel}。这会占用本地模型或 GPU，是否继续？`,
      )
    ) {
      return;
    }
    await runAction(run.id, () => startDramaProductionRun(run.id));
  }

  async function retry(run: DramaProductionRun) {
    if (
      !window.confirm(
        `只重试“${run.name}”中的 ${run.counts.failed} 个失败任务，`
        + "已成功和已绑定的素材不会重复生成。是否继续？",
      )
    ) {
      return;
    }
    await runAction(run.id, () => retryDramaProductionRun(run.id));
  }

  async function cancel(run: DramaProductionRun) {
    await runAction(run.id, () => cancelDramaProductionRun(run.id));
  }

  async function runAction(
    runId: string,
    action: () => Promise<DramaProductionRun>,
  ) {
    setBusyRunId(runId);
    setError("");
    try {
      const updated = await action();
      setRuns((items) =>
        items.map((run) => (run.id === runId ? updated : run)),
      );
      window.setTimeout(() => void refresh(), 400);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusyRunId(null);
    }
  }

  return (
    <section className="drama-run-panel">
      <header>
        <div>
          <span>批量制作运行</span>
          <small>部分失败可断点重试，已成功任务不会重复提交</small>
        </div>
        <div>
          <span>{visibleRuns.length} 个运行</span>
          {canceledCount > 0 && (
            <button
              type="button"
              onClick={() => setShowCanceled((current) => !current)}
            >
              {showCanceled ? "隐藏已取消" : `显示已取消 ${canceledCount}`}
            </button>
          )}
          <button type="button" onClick={() => void refresh()}>
            <RefreshCw className={loading ? "spin" : ""} size={14} />
            刷新
          </button>
          <button type="button" onClick={onOpenAgent}>
            <Bot size={14} />
            让 Agent 编排
          </button>
        </div>
      </header>

      {error && (
        <div className="drama-run-error">
          <TriangleAlert size={15} />
          {error}
        </div>
      )}

      {!visibleRuns.length && !loading ? (
        <div className="drama-run-empty">
          <Clock3 size={20} />
          <span>
            <strong>还没有批量运行</strong>
            <small>
              Agent 可以把当前阶段的镜头和资产组装成任务图，先预览再启动。
            </small>
          </span>
        </div>
      ) : (
        <div className="drama-run-list">
          {visibleRuns.map((run) => (
            <article className={run.status} key={run.id}>
              <div className="drama-run-head">
                <span className="drama-run-status-icon">
                  {run.status === "completed" ? (
                    <CheckCircle2 size={17} />
                  ) : ["failed", "partial"].includes(run.status) ? (
                    <TriangleAlert size={17} />
                  ) : ["queued", "running"].includes(run.status) ? (
                    <LoaderCircle
                      className={
                        run.status === "running" ? "spin" : undefined
                      }
                      size={17}
                    />
                  ) : (
                    <Clock3 size={17} />
                  )}
                </span>
                <div>
                  <strong>{run.name}</strong>
                  <small>
                    {runStatusLabel(run.status)} · 并行 {run.maxParallel}
                    {run.approvedBy ? ` · ${run.approvedBy}` : ""}
                  </small>
                </div>
                <div className="drama-run-counts">
                  <span>{run.counts.succeeded} 成功</span>
                  <span>{run.counts.failed} 失败</span>
                  <span>
                    {run.counts.pending + run.counts.queued + run.counts.running}
                    {" "}待处理
                  </span>
                  {Boolean(run.planning.skipped?.length) && (
                    <span>{run.planning.skipped?.length} 规划跳过</span>
                  )}
                </div>
                <div className="drama-run-actions">
                  {["draft", "awaiting_approval"].includes(run.status) && (
                    <button
                      type="button"
                      disabled={busyRunId === run.id}
                      onClick={() => void start(run)}
                    >
                      <Play size={13} />
                      确认并启动
                    </button>
                  )}
                  {["partial", "failed", "canceled"].includes(run.status) && (
                    <button
                      type="button"
                      disabled={busyRunId === run.id || run.counts.failed === 0}
                      onClick={() => void retry(run)}
                    >
                      <RotateCcw size={13} />
                      重试失败项
                    </button>
                  )}
                  {["queued", "running"].includes(run.status) && (
                    <button
                      type="button"
                      disabled={busyRunId === run.id}
                      onClick={() => void cancel(run)}
                    >
                      <Square size={12} />
                      取消
                    </button>
                  )}
                </div>
              </div>
              {(run.planning.skipped?.length ||
                run.planning.model?.name) && (
                <details className="drama-run-planning">
                  <summary>
                    <span>规划依据</span>
                    <small>
                      {run.planning.model?.name ?? "手动创建"}
                      {run.planning.skipped?.length
                        ? ` · ${run.planning.skipped.length} 项未进入本批次`
                        : " · 无跳过项"}
                    </small>
                  </summary>
                  {Boolean(run.planning.skipped?.length) && (
                    <div>
                      {run.planning.skipped?.map((item, index) => (
                        <p key={`${item.targetId}-${index}`}>
                          <code>{item.targetId.slice(0, 8)}</code>
                          {item.reason}
                        </p>
                      ))}
                    </div>
                  )}
                </details>
              )}
              <div className="drama-run-items">
                {run.items.map((item) => (
                  <RunItem item={item} key={item.id} />
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function RunItem({ item }: { item: DramaProductionRunItem }) {
  return (
    <div className={`drama-run-item ${item.status}`}>
      <span>{String(item.position + 1).padStart(2, "0")}</span>
      <div>
        <strong>{item.title || `${item.targetType} · ${item.slot}`}</strong>
        <small>
          {item.targetType} / {item.slot}
          {item.generationTaskId
            ? ` · task ${item.generationTaskId.slice(0, 8)}`
            : ""}
        </small>
      </div>
      <em>{itemStatusLabel(item.status)}</em>
      {item.error && <p>{item.error}</p>}
    </div>
  );
}

function runStatusLabel(status: DramaProductionRun["status"]) {
  return {
    draft: "草稿",
    awaiting_approval: "等待用户确认",
    queued: "已排队",
    running: "制作中",
    partial: "部分完成",
    completed: "全部完成",
    failed: "失败",
    canceled: "已取消",
  }[status];
}

function itemStatusLabel(status: DramaProductionRunItem["status"]) {
  return {
    pending: "等待",
    queued: "排队",
    running: "执行中",
    succeeded: "完成",
    failed: "失败",
    skipped: "跳过",
  }[status];
}
