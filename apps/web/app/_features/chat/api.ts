import { apiFetch, getJson, requireJson } from "../../_shared/api/client";
import type {
  ConversationHistory,
  ConversationSummary,
  SendMessageInput,
  ServerEvent,
} from "./types";

export function listConversations(signal?: AbortSignal) {
  return getJson<ConversationSummary[]>("/api/conversations", signal);
}

export async function createConversation(
  context?: {
    projectId?: string | null;
    episodeId?: string | null;
    scope?: string | null;
  },
) {
  return requireJson<{ id: string; title?: string }>(
    await apiFetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(context ?? {}),
    }),
  );
}

export function loadConversation(
  conversationId: string,
  cursor?: string | null,
  signal?: AbortSignal,
) {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return getJson<ConversationHistory>(
    `/api/conversations/${conversationId}/messages${query}`,
    signal,
  );
}

export async function interruptConversation(conversationId: string) {
  const response = await apiFetch(
    `/api/conversations/${conversationId}/interrupt`,
    { method: "POST" },
  );
  if (!response.ok) throw new Error("停止请求失败，请重试");
}

export async function streamMessage(
  input: SendMessageInput,
  onEvent: (event: ServerEvent) => void,
) {
  const response = await apiFetch(
    `/api/conversations/${input.conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: input.message,
        clientMessageId: input.clientMessageId,
        providerId: input.providerId,
        modelId: input.modelId,
      }),
      signal: input.signal,
    },
  );
  if (!response.ok || !response.body) {
    throw new Error("后端没有返回有效数据");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const dataLine = block
          .split("\n")
          .find((line) => line.startsWith("data: "));
        if (!dataLine) continue;
        const event = JSON.parse(dataLine.slice(6)) as ServerEvent;
        if (event.type === "done") completed = true;
        onEvent(event);
        if (event.type === "error") {
          throw new Error(event.message ?? "Codex 回复失败");
        }
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
  if (!completed) {
    throw new Error("连接提前结束，请重新打开会话查看结果");
  }
}
