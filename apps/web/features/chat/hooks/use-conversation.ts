"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../../shared/api/http";
import { conversationsApi } from "../api/conversations";
import { SessionSocket, sessionSocketUrl } from "../api/session-socket";
import { applyMessageEvent } from "../model/message-events";
import type { ConnectionStatus, Conversation, Message } from "../types";

const STORAGE_KEY = "zaojing-conversation";

export function useConversation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [connection, setConnection] =
    useState<ConnectionStatus>("disconnected");
  const session = useRef<{ id: string; client: SessionSocket } | null>(null);
  const selectedId = useRef<string | null>(null);
  const mounted = useRef(false);
  const busy = useRef(false);
  const stopRequested = useRef(false);
  const historyRequest = useRef<AbortController | null>(null);
  const createRequest = useRef<AbortController | null>(null);
  const projectId = useRef<string | null>(null);

  const refreshList = useCallback(async (signal?: AbortSignal) => {
    try {
      const list = await conversationsApi.list(signal);
      if (mounted.current && !signal?.aborted) setConversations(list);
    } catch (error) {
      if (mounted.current && !signal?.aborted) setNotice(errorMessage(error));
    }
  }, []);

  const connect = useCallback((id: string) => {
    if (session.current?.id !== id) {
      session.current?.client.close();
      const client = new SessionSocket(
        sessionSocketUrl(id, window.location),
        (status) => {
          if (mounted.current && selectedId.current === id)
            setConnection(status);
        },
        (error) => {
          if (mounted.current && selectedId.current === id)
            setNotice(error.message);
        },
      );
      session.current = { id, client };
    }
    return session.current.client.connect();
  }, []);

  const selectConversation = useCallback(
    async (id: string, cursor?: string | null) => {
      if (busy.current) return;
      historyRequest.current?.abort();
      const controller = new AbortController();
      historyRequest.current = controller;
      setLoading(true);
      setNotice("");
      try {
        const history = await conversationsApi.history(
          id,
          cursor,
          controller.signal,
        );
        if (controller.signal.aborted || !mounted.current) return;
        selectedId.current = id;
        setConversationId(id);
        setMessages((current) =>
          cursor ? [...history.messages, ...current] : history.messages,
        );
        setCursor(history.cursor);
        localStorage.setItem(STORAGE_KEY, id);
        setNotice(history.active ? "此会话仍在回复，请稍后重新打开。" : "");
        await connect(id);
      } catch (error) {
        if (!controller.signal.aborted && mounted.current)
          setNotice(errorMessage(error));
      } finally {
        if (!controller.signal.aborted && mounted.current) setLoading(false);
      }
    },
    [connect],
  );

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refreshList(controller.signal);
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) void selectConversation(saved);
    return () => {
      mounted.current = false;
      controller.abort();
      historyRequest.current?.abort();
      createRequest.current?.abort();
      session.current?.client.close();
      session.current = null;
    };
  }, [refreshList, selectConversation]);

  function newConversation() {
    if (busy.current) return;
    historyRequest.current?.abort();
    session.current?.client.close();
    session.current = null;
    selectedId.current = null;
    localStorage.removeItem(STORAGE_KEY);
    setConversationId(null);
    setMessages([]);
    setCursor(null);
    setNotice("");
    projectId.current = null;
    setLoading(false);
  }

  async function sendMessage(
    text: string,
    model: { id: string; providerId: string },
    creativeProjectId?: string | null,
  ) {
    const message = text.trim();
    if (!message || busy.current || loading) return;
    busy.current = true;
    stopRequested.current = false;
    setIsSending(true);
    setNotice("");
    const user: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };
    let assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      user,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
      },
    ]);
    try {
      let id = selectedId.current;
      if (!id) {
        const controller = new AbortController();
        createRequest.current = controller;
        const created = await conversationsApi.create(controller.signal);
        if (!mounted.current) return;
        id = created.id;
        selectedId.current = id;
        setConversationId(id);
        localStorage.setItem(STORAGE_KEY, id);
      }
      await connect(id);
      if (!mounted.current) return;
      const client = session.current!.client;
      const completion = client.send(
        {
          message,
          clientMessageId: user.id,
          modelId: model.id,
          providerId: model.providerId,
          projectId: creativeProjectId || projectId.current || undefined,
        },
        (event) => {
          const previousId = assistantId;
          if (event.type === "meta" && event.assistantMessageId)
            assistantId = event.assistantMessageId;
          setMessages((current) =>
            current.map((item) =>
              item.id === previousId ? applyMessageEvent(item, event) : item,
            ),
          );
          if (event.type === "done" && event.status === "interrupted")
            setNotice("回复已停止");
          if (event.type === "project_sync") {
            const count = event.changedArtifacts.length;
            setNotice(
              count
                ? `项目已同步，更新了 ${count} 个阶段产物。`
                : "项目已同步，阶段文件没有新增变化。",
            );
          }
          if (event.type === "control_error") setNotice(event.message);
        },
      );
      if (stopRequested.current) client.interrupt();
      await completion;
    } catch (error) {
      if (mounted.current) {
        setNotice(errorMessage(error));
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId ? { ...item, status: "error" } : item,
          ),
        );
      }
    } finally {
      busy.current = false;
      if (mounted.current) {
        setIsSending(false);
        void refreshList();
      }
    }
  }

  function interrupt() {
    stopRequested.current = true;
    session.current?.client.interrupt();
  }

  async function reconnect() {
    if (!selectedId.current) return;
    await selectConversation(selectedId.current);
  }

  return {
    messages,
    conversations,
    conversationId,
    cursor,
    notice,
    loading,
    isSending,
    connection,
    selectConversation,
    newConversation,
    sendMessage,
    interrupt,
    reconnect,
  };
}
