"use client";

import { Bot, Menu, Plus } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../_features/chat/types";
import { Composer } from "../conversation/Composer";
import { MessageList } from "../conversation/MessageList";

type ChatViewProps = {
  messages: ChatMessage[];
  cursor: string | null;
  notice: string;
  input: string;
  selectedModelName: string;
  conversationTitle: string;
  isSending: boolean;
  canSend: boolean;
  onChangeInput: (value: string) => void;
  onLoadOlder: () => void;
  onNewConversation: () => void;
  onOpenHistory: () => void;
  onOpenSettings: () => void;
  onSend: () => void;
  onStop: () => void;
  onToggleReasoning: (messageId: string) => void;
};

export function ChatView({
  messages,
  cursor,
  notice,
  input,
  selectedModelName,
  conversationTitle,
  isSending,
  canSend,
  onChangeInput,
  onLoadOlder,
  onNewConversation,
  onOpenHistory,
  onOpenSettings,
  onSend,
  onStop,
  onToggleReasoning,
}: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <button
            className="mobile-menu"
            type="button"
            title="打开导航"
            onClick={onOpenHistory}
          >
            <Menu size={20} />
          </button>
          <span className="chat-mark">
            <Bot size={17} />
          </span>
          <div className="chat-title-copy">
            <small>创意 Agent · 本地 Codex</small>
            <h1 title={conversationTitle}>{conversationTitle}</h1>
          </div>
        </div>
        <div className="chat-header-actions">
          <span className={`chat-runtime ${isSending ? "busy" : ""}`}>
            <i />
            {isSending ? "Agent 正在执行" : "等待输入"}
          </span>
          <button
            className="header-new"
            type="button"
            onClick={onNewConversation}
          >
            <Plus size={16} />
            新对话
          </button>
        </div>
      </header>
      <div className="conversation-area">
        <MessageList
          messages={messages}
          cursor={cursor}
          bottomRef={bottomRef}
          onLoadOlder={onLoadOlder}
          onToggleReasoning={onToggleReasoning}
        />
      </div>
      <div className="composer-dock">
        {notice && (
          <p className="notice" role="alert">
            {notice}
          </p>
        )}
        <Composer
          compact
          input={input}
          selectedModelName={selectedModelName}
          isSending={isSending}
          canSend={canSend}
          onChangeInput={onChangeInput}
          onOpenSettings={onOpenSettings}
          onSend={onSend}
          onStop={onStop}
        />
        <p>Agent 可能会犯错，请核对重要信息</p>
      </div>
    </section>
  );
}
