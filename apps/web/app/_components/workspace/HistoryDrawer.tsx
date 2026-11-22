import { MessageSquareText, Plus, Sparkles } from "lucide-react";
import type { ConversationSummary } from "../../_features/chat/types";

type HistoryDrawerProps = {
  open: boolean;
  variant?: "drawer" | "rail";
  conversations: ConversationSummary[];
  conversationId: string | null;
  connected: boolean;
  isSending: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSelect: (id: string) => void;
};

export function HistoryDrawer({
  open,
  variant = "drawer",
  conversations,
  conversationId,
  connected,
  isSending,
  onClose,
  onNewConversation,
  onSelect,
}: HistoryDrawerProps) {
  return (
    <aside
      className={`history-drawer ${variant === "rail" ? "rail" : ""} ${
        open ? "open" : ""
      }`}
      aria-hidden={variant === "drawer" ? !open : undefined}
      aria-label={variant === "rail" ? "历史对话" : undefined}
    >
      <div className="drawer-head">
        <div>
          <Sparkles size={18} />
          <strong>{variant === "rail" ? "对话记录" : "造境"}</strong>
        </div>
        {variant === "drawer" && (
          <button type="button" title="关闭" onClick={onClose}>
            ×
          </button>
        )}
      </div>
      <button
        className="new-chat"
        type="button"
        disabled={isSending}
        onClick={onNewConversation}
      >
        <Plus size={17} />
        新建对话
      </button>
      <span className="drawer-label">
        最近对话
        {conversations.length > 0 && <small>{conversations.length}</small>}
      </span>
      <div className="conversation-list">
        {conversations.map((conversation) => (
          <button
            key={conversation.threadId ?? conversation.id}
            disabled={isSending}
            className={`conversation ${
              conversation.id === conversationId ? "active" : ""
            }`}
            type="button"
            onClick={() => onSelect(conversation.id)}
          >
            <MessageSquareText size={16} />
            <span className="conversation-copy">
              <strong>{conversation.title}</strong>
              <small>
                {conversation.scope
                  ? `${conversation.scope} · ${
                      conversation.episodeId
                        ? `episode ${conversation.episodeId.slice(0, 8)}`
                        : "project"
                    } · `
                  : ""}
                {conversation.threadId
                  ? `Thread ${conversation.threadId.slice(0, 8)} · ${
                      conversation.messageCount ?? 0
                    } 条消息${
                      conversation.status === "running" ? " · 执行中" : ""
                    }`
                  : `${conversation.messageCount ?? 0} 条消息`}
              </small>
            </span>
          </button>
        ))}
      </div>
      <div className="connection">
        <span className={connected ? "online" : ""} />
        <div>
          <strong>{connected ? "Codex 已连接" : "Codex 未连接"}</strong>
          <small>本地 App Server</small>
        </div>
      </div>
    </aside>
  );
}
