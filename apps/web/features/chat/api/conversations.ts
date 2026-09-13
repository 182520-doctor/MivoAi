import { requestJson } from "../../../shared/api/http";
import type { Conversation, ConversationHistory } from "../types";

export const conversationsApi = {
  list: (signal?: AbortSignal) =>
    requestJson<Conversation[]>("/api/conversations", { signal }),
  create: (signal?: AbortSignal) =>
    requestJson<Conversation>("/api/conversations", {
      method: "POST",
      signal,
    }),
  history: (id: string, cursor?: string | null, signal?: AbortSignal) => {
    const query = cursor ? `?${new URLSearchParams({ cursor })}` : "";
    return requestJson<ConversationHistory>(
      `/api/conversations/${encodeURIComponent(id)}/messages${query}`,
      { signal },
    );
  },
};
