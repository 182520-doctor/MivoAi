"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, Sparkles } from "lucide-react";
import { MarkdownContent } from "../../../shared/ui/markdown-content";
import type { Message } from "../types";

function ReasoningPanel({ message }: { message: Message }) {
  const [open, setOpen] = useState(message.status === "streaming");
  if (
    !message.reasoning &&
    !message.reasoningTokens &&
    message.status !== "streaming"
  )
    return null;
  return (
    <div className={`reasoning-panel ${open ? "open" : ""}`}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronDown size={14} />
        <span>
          {message.status === "streaming" && !message.content
            ? "正在思考"
            : "思考过程"}
        </span>
      </button>
      {open && (
        <div className="reasoning-body">
          <MarkdownContent>
            {message.reasoning ||
              (message.status === "streaming" ? "思考中…" : "暂无思考摘要")}
          </MarkdownContent>
        </div>
      )}
    </div>
  );
}

type Props = {
  messages: Message[];
  hasMore: boolean;
  loading: boolean;
  onLoadMore: () => void;
};

export function MessageList({ messages, hasMore, loading, onLoadMore }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  useEffect(() => {
    const area = scrollRef.current;
    if (area && follow.current) area.scrollTop = area.scrollHeight;
  }, [messages]);
  return (
    <div
      className="conversation-area"
      ref={scrollRef}
      onScroll={() => {
        const area = scrollRef.current;
        if (area)
          follow.current =
            area.scrollHeight - area.scrollTop - area.clientHeight < 100;
      }}
    >
      <div className="message-list">
        {hasMore && (
          <button className="load-more" disabled={loading} onClick={onLoadMore}>
            加载更早消息
          </button>
        )}
        {messages.map((message) => (
          <article className={`message ${message.role}`} key={message.id}>
            {message.role === "assistant" && (
              <div className="avatar">
                <Sparkles size={15} />
              </div>
            )}
            <div className="message-content">
              {message.role === "assistant" && (
                <>
                  <span className="message-author">造境 Agent</span>
                  <ReasoningPanel message={message} />
                </>
              )}
              {message.content && (
                <div className="markdown">
                  <MarkdownContent>{message.content}</MarkdownContent>
                </div>
              )}
              {message.role === "assistant" &&
                message.status === "streaming" && (
                  <span className="typing-dot" />
                )}
              {message.role === "assistant" && message.status === "done" && (
                <span className="message-status">
                  <CheckCircle2 size={13} />
                  已完成
                </span>
              )}
              {message.status === "error" && (
                <span className="message-error">回复未完成</span>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
