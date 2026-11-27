"use client";

import { ArrowUpRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useHealthStatus } from "../../_features/health/useHealthStatus";
import { AppSidebar } from "./AppSidebar";
import { ThemeProvider } from "./ThemeProvider";

export function StudioFrame({ children }: { children: ReactNode }) {
  const { connected } = useHealthStatus();
  const pathname = usePathname();

  return (
    <ThemeProvider>
      <div className="studio-frame">
        <AppSidebar connected={connected} />
        <div className="studio-main">
          <header className="studio-mobile-toolbar">
            <Link className="studio-mobile-brand" href="/">
              <span className="studio-mobile-brand-mark">
                <Sparkles size={16} />
              </span>
              <span>
                <strong>造境</strong>
                <small>{routeLabel(pathname)}</small>
              </span>
            </Link>
            <div className="studio-mobile-toolbar-actions">
              <span
                className={`studio-mobile-health ${connected ? "online" : ""}`}
              >
                <i />
                {connected ? "已连接" : "离线"}
              </span>
              {pathname !== "/chat" && (
                <Link className="studio-mobile-create" href="/chat">
                  新对话
                  <ArrowUpRight size={14} />
                </Link>
              )}
            </div>
          </header>
          {children}
        </div>
      </div>
    </ThemeProvider>
  );
}

function routeLabel(pathname: string) {
  if (pathname === "/") return "工作台总览";
  if (pathname.startsWith("/chat")) return "Agent 对话";
  if (pathname.startsWith("/media")) return "多模态创作";
  if (pathname.startsWith("/drama")) return "短剧制作";
  if (pathname.startsWith("/models")) return "模型与接入";
  if (pathname.startsWith("/assets")) return "素材库";
  if (pathname.startsWith("/tasks")) return "任务中心";
  return "创作系统";
}
