"use client";

import { useCallback, useEffect, useState } from "react";
import { listConversations } from "./api";
import type { ConversationSummary } from "./types";

export function useConversationList() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      setConversations(await listConversations());
    } catch {
      // Health and chat notices already communicate connection failures.
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { conversations, refresh };
}
