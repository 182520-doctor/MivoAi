"use client";

import { useCallback, useEffect, useState } from "react";
import { loadHealth } from "./api";
import type { Health } from "./types";

export function useHealthStatus() {
  const [health, setHealth] = useState<Health | null>(null);

  const check = useCallback(async () => {
    try {
      setHealth(await loadHealth());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = window.setInterval(() => void check(), 5000);
    return () => window.clearInterval(timer);
  }, [check]);

  return {
    health,
    connected: health?.status === "ok" && health.app_server.running,
    accountAuthenticated: health?.app_server.authenticated ?? false,
  };
}
