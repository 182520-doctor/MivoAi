"use client";

import {
  Bot,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Clapperboard,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import type { DramaProductionRole } from "../../_features/drama/types";
import { useDramaControlRoom } from "../../_features/drama/useDramaControlRoom";
import { DramaProductionRunPanel } from "./DramaProductionRunPanel";

type DramaControlRoomProps = {
  projectId: string;
  episodeId?: string | null;
  stage: string;
  onOpenAgent: (context?: string) => void;
  onApproved?: () => void;
  refreshToken?: number;
};

export function DramaControlRoom({
  projectId,
  episodeId,
  stage,
  onOpenAgent,
  onApproved,
  refreshToken = 0,
}: DramaControlRoomProps) {
  const control = useDramaControlRoom(projectId);
  const [feedback, setFeedback] = useState("");
  const room = control.controlRoom;
  const gate = room?.gates.find((item) => item.stage === stage);
  const roles =
    room?.roles.filter((role) => gate?.ownerRoleIds.includes(role.id)) ?? [];
  const openReviews =
    gate &&
    Object.values(gate.latestReviews).filter(
      (review) =>
        review.status === "failed" ||
        review.status === "changes_requested",
    );

  async function approve() {
    if (!gate) return;
    const approved = await control.approve(stage, feedback);
    if (approved) {
      setFeedback("");
      onApproved?.();
    }
  }

  async function requestChanges() {
    if (!gate || !feedback.trim()) return;
    await control.requestChanges(stage, feedback.trim());
  }

  return (
    <section className="drama-control-room">
      <header className="drama-control-room-head">
        <div>
          <span className="eyebrow">Production Control</span>
          <h3>制作控制室</h3>
          <p>
            Agent 按专业角色完成检查和草稿，由你确认本阶段是否放行。
          </p>
        </div>
        <div className="drama-control-actions">
          <button type="button" onClick={() => onOpenAgent()}>
            <Bot size={14} /> 在 Agent 中继续
          </button>
          <button
            type="button"
            title="刷新制作状态"
            onClick={() => void control.refresh()}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </header>

      <DramaProductionRunPanel
        projectId={projectId}
        stage={stage}
        episodeId={episodeId}
        refreshToken={refreshToken}
        onOpenAgent={() => onOpenAgent(planBatchPrompt(stage))}
      />

      {room && gate ? (
        <>
          <div className="drama-gate-summary">
            <div className={`drama-gate-seal ${gate.status}`}>
              {gate.approved ? (
                <ShieldCheck size={19} />
              ) : gate.status === "failed" ||
                gate.status === "changes_requested" ? (
                <CircleAlert size={19} />
              ) : (
                <ClipboardCheck size={19} />
              )}
              <span>
                <small>当前质量门</small>
                <strong>{gate.label}</strong>
              </span>
            </div>
            <div>
              <small>Agent 角色审核</small>
              <strong>
                {gate.agentReady
                  ? "角色审核已齐"
                  : `${Object.keys(gate.latestReviews).length} / ${gate.ownerRoleIds.length} 已提交`}
              </strong>
            </div>
            <div>
              <small>平均评分</small>
              <strong>{gate.score ?? "—"}</strong>
            </div>
            <div>
              <small>用户确认</small>
              <strong>
                {gate.stale
                  ? "需重新确认"
                  : gate.approved
                    ? "已通过"
                    : "等待确认"}
              </strong>
            </div>
          </div>

          <div className="drama-role-grid">
            {roles.map((role) => (
              <RoleCard
                key={role.id}
                role={role}
                review={gate.latestReviews[role.id]}
              />
            ))}
          </div>

          {openReviews?.length ? (
            <div className="drama-gate-blockers">
              <CircleAlert size={17} />
              <div>
                <strong>本阶段还有 {openReviews.length} 项待处理</strong>
                {openReviews.map((review) => (
                  <p key={review.id}>{review.feedback || review.roleId}</p>
                ))}
              </div>
            </div>
          ) : null}

          <div className="drama-gate-decision">
            <label>
              <span>给 Agent / 角色的确认意见</span>
              <input
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
                placeholder="例如：风格可以，但第 2 集冲突还不够明确"
              />
            </label>
            <button
              type="button"
              disabled={control.saving || !feedback.trim()}
              onClick={() => void requestChanges()}
            >
              <MessageSquareText size={14} /> 要求修改
            </button>
            <button
              className="primary"
              type="button"
              disabled={control.saving || gate.approved || !gate.agentReady}
              onClick={() => void approve()}
            >
              {control.saving ? (
                <LoaderCircle className="spin" size={14} />
              ) : (
                <CheckCircle2 size={14} />
              )}
              {gate.approved
                ? "本阶段已确认"
                : gate.agentReady
                  ? "确认本阶段并继续"
                  : "等待角色审核"}
            </button>
          </div>

          <div className="drama-episode-check">
            <div className="drama-episode-check-head">
              <span>
                <Clapperboard size={15} /> 分集制作检查
              </span>
              <small>
                {room.episodes.filter((episode) => episode.planComplete).length}
                {" / "}
                {room.episodes.length} 集计划完整
              </small>
            </div>
            {room.episodes.length ? (
              <div className="drama-episode-check-grid">
                {room.episodes.map((episode) => (
                  <article
                    key={episode.id}
                    className={episode.planComplete ? "complete" : ""}
                  >
                    <header>
                      <span>第 {episode.episodeNumber} 集</span>
                      <strong>{episode.title}</strong>
                      {episode.planComplete ? (
                        <CheckCircle2 size={15} />
                      ) : (
                        <CircleAlert size={15} />
                      )}
                    </header>
                    <div>
                      <span>
                        时间
                        <strong>{episode.plan.timeScope || "待拆解"}</strong>
                      </span>
                      <span>
                        人物
                        <strong>
                          {episode.plan.characters.join("、") || "待拆解"}
                        </strong>
                      </span>
                      <span>
                        场景
                        <strong>
                          {episode.plan.scenes.join("、") || "待拆解"}
                        </strong>
                      </span>
                    </div>
                    <p>
                      {episode.plan.storyBeats.join(" → ") ||
                        "尚无故事节拍，Agent 需要先完成逐集拆解。"}
                    </p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="drama-episode-check-empty">
                还没有分集。先与 Agent 确认集数，再生成逐集计划。
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="drama-control-loading">
          <LoaderCircle className="spin" size={18} />
          {control.loading ? "正在读取制作控制室…" : "制作控制室暂不可用"}
        </div>
      )}

      {(control.notice || control.loading) && (
        <footer className="drama-control-foot">
          {control.loading ? "正在刷新制作状态…" : control.notice}
        </footer>
      )}
    </section>
  );
}

function RoleCard({
  role,
  review,
}: {
  role: DramaProductionRole;
  review?: {
    status: "pending" | "passed" | "changes_requested" | "failed";
    score: number;
    feedback: string;
  };
}) {
  return (
    <details className={`drama-role-card ${review?.status ?? "unreviewed"}`}>
      <summary>
        <span>
          <UsersRound size={15} />
        </span>
        <div>
          <strong>{role.title}</strong>
          <small>{role.department}</small>
        </div>
        <em>
          {review
            ? review.status === "passed"
              ? `${review.score} 分`
              : review.status === "changes_requested"
                ? "需修改"
                : review.status === "failed"
                  ? "未通过"
                  : "待审核"
            : "未审核"}
        </em>
      </summary>
      <div className="drama-role-card-body">
        <p>{role.description}</p>
        <section>
          <span>专业检查</span>
          <ul>
            {role.checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <span>交付物</span>
          <ul>
            {role.deliverables.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        {review?.feedback && <blockquote>{review.feedback}</blockquote>}
      </div>
    </details>
  );
}

function planBatchPrompt(stage: string) {
  return [
    `请为当前分集的 ${stage} 阶段规划批量制作。`,
    "先调用 zaojing_get_drama_episode 检查镜头、实体引用和缺失槽位。",
    "再调用 zaojing_discover_media_models 选择合适的已配置模型。",
    "然后调用 zaojing_plan_drama_production_run 自动创建任务图；只规划，不启动。",
    "创建后展示任务数量、模型、跳过项和每个镜头槽位，等待我明确确认后再启动。",
  ].join("\n");
}
