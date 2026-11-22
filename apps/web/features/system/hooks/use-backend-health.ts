"use client";

import { useEffect, useState } from "react";
import { readHealth } from "../api/health";

export function useBackendHealth() {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const health = await readHealth(controller.signal);
        if (!controller.signal.aborted) {
          setConnected(
            health.status === "ok" && health.app_server.authenticated,
          );
        }
      } catch {
        if (!controller.signal.aborted) setConnected(false);
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 5000);
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);
  return connected;
}
