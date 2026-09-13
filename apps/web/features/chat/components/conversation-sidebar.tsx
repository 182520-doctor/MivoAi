"use client";

import { MessageSquareText, Plus, RefreshCw, Sparkles, X } from "lucide-react";
import type { ConnectionStatus, Conversation } from "../types";

type Props = {
  open: boolean;
  busy: boolean;
  loading: boolean;
  conversations: Conversation[];
  selectedId: string | null;
  connection: ConnectionStatus;
  onClose: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onReconnect: () => void;
};

export function ConversationSidebar(props: Props) {
  const {
    open,
    busy,
    loading,
    conversations,
    selectedId,
    connection,
    onClose,
    onNew,
    onSelect,
    onReconnect,
  } = props;
  return (
    <>
      {open && (
        <button
          className="drawer-backdrop"
          type="button"
          aria-label="关闭会话列表"
          onClick={onClose}
        />
      )}
      <aside
        className={`history-drawer ${open ? "open" : ""}`}
        aria-label="会话列表"
      >
        <div className="drawer-head">
          <div>
            <Sparkles size={18} />
            <strong>造境</strong>
          </div>
          <button type="button" title="关闭" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <button
          className="new-chat"
          type="button"
          disabled={busy}
          onClick={onNew}
        >
          <Plus size={17} />
          新建对话
        </button>
        <span className="drawer-label">最近对话</span>
        <div className="conversation-list" aria-busy={loading}>
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              disabled={busy}
              className={`conversation ${conversation.id === selectedId ? "active" : ""}`}
              type="button"
              onClick={() => onSelect(conversation.id)}
            >
              <MessageSquareText size={16} />
              <span>{conversation.title}</span>
            </button>
          ))}
        </div>
        <div className="connection">
          <span className={connection === "connected" ? "online" : ""} />
          <div>
            <strong>
              {connection === "connected"
                ? "会话已连接"
                : connection === "connecting"
                  ? "连接中"
                  : "会话未连接"}
            </strong>
            <small>造境 Agent</small>
          </div>
          {selectedId && connection === "disconnected" && (
            <button
              type="button"
              title="重新连接"
              disabled={busy}
              onClick={onReconnect}
            >
              <RefreshCw size={16} />
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
