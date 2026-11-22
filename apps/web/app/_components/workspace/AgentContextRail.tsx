import {
  Bot,
  Cpu,
  FolderOpen,
  Images,
  Radio,
  Video,
  Wrench,
} from "lucide-react";

type AgentContextRailProps = {
  conversationId: string | null;
  conversationStatus?: string;
  workspace?: string | null;
  selectedModelName: string;
  connected: boolean;
  isSending: boolean;
};

export function AgentContextRail({
  conversationId,
  conversationStatus,
  workspace,
  selectedModelName,
  connected,
  isSending,
}: AgentContextRailProps) {
  const state = isSending
    ? { label: "正在执行", className: "busy" }
    : connected
      ? { label: "等待输入", className: "ready" }
      : { label: "连接不可用", className: "offline" };

  return (
    <aside className="agent-context-rail" aria-label="本次会话上下文">
      <header className="context-rail-head">
        <span>Agent 工作台</span>
        <strong>会话上下文</strong>
      </header>

      <div className={`context-state ${state.className}`}>
        <Radio size={18} />
        <div>
          <small>运行状态</small>
          <strong>{state.label}</strong>
        </div>
      </div>

      <section className="context-section">
        <span className="context-section-label">执行环境</span>
        <div className="context-info-row">
          <Bot size={15} />
          <div>
            <small>Agent</small>
            <strong>{connected ? "本地 Codex" : "未连接"}</strong>
          </div>
        </div>
        <div className="context-info-row">
          <Cpu size={15} />
          <div>
            <small>当前模型</small>
            <strong title={selectedModelName}>{selectedModelName}</strong>
          </div>
        </div>
        <div className="context-info-row">
          <FolderOpen size={15} />
          <div>
            <small>会话工作区</small>
            <code title={workspace ?? undefined}>
              {workspace ?? "提交首条消息后创建"}
            </code>
          </div>
        </div>
      </section>

      <section className="context-section">
        <span className="context-section-label">会话信息</span>
        <dl className="context-meta">
          <div>
            <dt>会话状态</dt>
            <dd>{conversationStatus ?? "idle"}</dd>
          </div>
          <div>
            <dt>会话 ID</dt>
            <dd>{conversationId ? conversationId.slice(0, 8) : "待创建"}</dd>
          </div>
        </dl>
      </section>

      <section className="context-section">
        <span className="context-section-label">可用工具</span>
        <div className="context-tools">
          <span>
            <Images size={14} /> 图片生成
          </span>
          <span>
            <Video size={14} /> 视频生成
          </span>
          <span>
            <Wrench size={14} /> 工作流发现
          </span>
        </div>
      </section>

      <p className="context-rail-note">
        Agent 会自动发现工具、组装参数、执行任务并继续本次会话。
      </p>
    </aside>
  );
}
