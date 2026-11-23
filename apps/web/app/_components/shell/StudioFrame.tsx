"use client";

import type { ReactNode } from "react";
import { useHealthStatus } from "../../_features/health/useHealthStatus";
import { AppSidebar } from "./AppSidebar";
import { ThemeProvider } from "./ThemeProvider";

export function StudioFrame({ children }: { children: ReactNode }) {
  const { connected } = useHealthStatus();

  return (
    <ThemeProvider>
      <div className="studio-frame">
        <AppSidebar connected={connected} />
        <div className="studio-main">{children}</div>
      </div>
    </ThemeProvider>
  );
}
