"use client";

import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  interruptConversation,
  loadConversation,
  streamMessage,
} from "./api";
import { applyServerEvent } from "./streamReducer";
import type { ChatMessage } from "./types";
import type { Model } from "../models/types";

type ChatSessionOptions = {
  selectedModel: Model | undefined;
  onConversationsChanged: () => Promise<void>;
  storageKey?: string;
  initialPromptFromUrl?: boolean;
  newConversationContext?: {
    projectId?: string | null;
    episodeId?: string | null;
    scope?: string | null;
  };
};

export function useChatSession({
  selectedModel,
  onConversationsChanged,
  storageKey = "zaojing-conversation",
  initialPromptFromUrl = true,
  newConversationContext,
}: ChatSessionOptions) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [isSending, setIsSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function patchAssistant(
    assistantId: string,
    updater: (message: ChatMessage) => ChatMessage,
  ) {
    setMessages((current) =>
      current.map((item) => (item.id === assistantId ? updater(item) : item)),
    );
  }

  async function selectConversation(id: string, older = false) {
    try {
      const data = await loadConversation(id, older ? cursor : null);
      setConversationId(id);
      localStorage.setItem(storageKey, id);
      setMessages((current) =>
        older
          ? [...data.messages.map(stripDramaContext), ...current]
          : data.messages.map(stripDramaContext),
      );
      setCursor(data.cursor);
      setNotice(data.active ? "此会话仍在回复，请稍后刷新会话。" : "");
    } catch (error) {
      setNotice((error as Error).message);
    }
  }

  useEffect(() => {
    setMessages([]);
    setConversationId(null);
    setCursor(null);
    setNotice("");
    setInput("");
    if (initialPromptFromUrl) {
      const params = new URLSearchParams(window.location.search);
      const initialPrompt = params.get("prompt")?.trim();
      if (initialPrompt) {
        setInput(initialPrompt);
        window.history.replaceState({}, "", "/chat");
        return;
      }
    }
    const saved = localStorage.getItem(storageKey);
    if (saved) void selectConversation(saved);
    // The saved conversation is restored when the scoped thread key changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey, initialPromptFromUrl]);

  function newConversation() {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    localStorage.removeItem(storageKey);
    setCursor(null);
    setNotice("");
    setInput("");
    setIsSending(false);
  }

  async function sendMessage(text: string, hiddenContext = "") {
    const message = text.trim();
    if (!message || isSending) return;
    const transportMessage = hiddenContext.trim()
      ? `${hiddenContext.trim()}\n\n用户消息：\n${message}`
      : message;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: "assistant", content: "", status: "streaming" },
    ]);
    setInput("");
    setIsSending(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let currentAssistantId = assistantId;
    try {
      let cid = conversationId;
      if (!cid) {
        const created = await createConversation(newConversationContext);
        cid = created.id;
        setConversationId(cid);
        localStorage.setItem(storageKey, cid);
      }
      await streamMessage(
        {
          conversationId: cid,
          message: transportMessage,
          clientMessageId: userMessage.id,
          providerId: selectedModel?.providerId ?? "codex_local",
          modelId: selectedModel?.id ?? "codex-local-default",
          signal: controller.signal,
        },
        (event) => {
          if (event.type === "meta" && event.assistantMessageId) {
            const previousId = currentAssistantId;
            const nextId = event.assistantMessageId;
            currentAssistantId = nextId;
            setMessages((current) =>
              current.map((item) =>
                item.id === previousId ? { ...item, id: nextId } : item,
              ),
            );
            return;
          }
          if (event.type === "done" && event.status === "interrupted") {
            setNotice("回复已停止");
          }
          patchAssistant(currentAssistantId, (item) =>
            applyServerEvent(item, event),
          );
        },
      );
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        const messageText = (error as Error).message;
        setNotice(messageText);
        setMessages((current) =>
          current.map((item) =>
            item.id === currentAssistantId
              ? { ...item, status: "error", content: item.content || messageText }
              : item,
          ),
        );
      }
    } finally {
      setIsSending(false);
      abortRef.current = null;
      await onConversationsChanged();
    }
  }

  async function stopReply() {
    if (!conversationId) return;
    try {
      await interruptConversation(conversationId);
    } catch (error) {
      setNotice((error as Error).message);
    }
  }

  function toggleReasoning(messageId: string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? { ...message, reasoningOpen: !message.reasoningOpen }
          : message,
      ),
    );
  }

  return {
    input,
    setInput,
    messages,
    conversationId,
    cursor,
    notice,
    isSending,
    selectConversation,
    newConversation,
    sendMessage,
    stopReply,
    toggleReasoning,
  };
}

function stripDramaContext(message: ChatMessage): ChatMessage {
  if (
    message.role !== "user"
    || !message.content.startsWith("【短剧工作台上下文】")
  ) {
    return message;
  }
  const marker = "\n\n用户消息：\n";
  const index = message.content.indexOf(marker);
  return {
    ...message,
    content:
      index >= 0
        ? message.content.slice(index + marker.length)
        : message.content,
  };
}
