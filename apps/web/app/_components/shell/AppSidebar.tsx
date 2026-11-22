"use client";

import {
  Clapperboard,
  Cpu,
  FolderOpen,
  Image as ImageIcon,
  LayoutDashboard,
  ListTodo,
  MessageSquareText,
  Moon,
  MoreHorizontal,
  Plus,
  Sparkles,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAppTheme } from "./ThemeProvider";

const navigation = [
  {
    label: "工作台",
    items: [
      { href: "/", label: "总览", mobileLabel: "总览", icon: LayoutDashboard },
      {
        href: "/chat",
        label: "Agent 对话",
        mobileLabel: "Agent",
        icon: MessageSquareText,
      },
    ],
  },
  {
    label: "创作",
    items: [
      {
        href: "/media",
        label: "多模态创作",
        mobileLabel: "创作",
        icon: ImageIcon,
      },
      {
        href: "/drama",
        label: "短剧制作",
        mobileLabel: "短剧",
        icon: Clapperboard,
      },
    ],
  },
  {
    label: "管理",
    items: [
      {
        href: "/models",
        label: "模型与接入",
        mobileLabel: "模型",
        icon: Cpu,
      },
      {
        href: "/assets",
        label: "素材库",
        mobileLabel: "素材",
        icon: FolderOpen,
        secondary: true,
      },
      {
        href: "/tasks",
        label: "任务中心",
        mobileLabel: "任务",
        icon: ListTodo,
        secondary: true,
      },
    ],
  },
];

type AppSidebarProps = {
  connected: boolean;
};

export function AppSidebar({ connected }: AppSidebarProps) {
  const pathname = usePathname();
  const { theme, setTheme } = useAppTheme();
  const [moreOpen, setMoreOpen] = useState(false);
  const secondaryItems = navigation.flatMap((group) =>
    group.items.filter((item) => "secondary" in item && item.secondary),
  );

  return (
    <aside className="studio-sidebar">
      <Link className="studio-brand" href="/">
        <span className="studio-brand-mark">
          <Sparkles size={22} />
        </span>
        <span className="studio-brand-copy">
          <strong>造境</strong>
          <small>Agent 创作系统</small>
        </span>
        <span className="studio-version">MVP</span>
      </Link>

      <Link className="studio-create" href="/chat">
        <span className="studio-create-icon">
          <Plus size={17} />
        </span>
        <span>
          <strong>新建创作</strong>
          <small>从一句想法开始</small>
        </span>
      </Link>

      <nav className="studio-nav" aria-label="产品导航">
        {navigation.map((group) => (
          <div className="studio-nav-group" key={group.label}>
            <span className="studio-nav-label">{group.label}</span>
            <div className="studio-nav-items">
              {group.items.map(
                ({ href, label, mobileLabel, icon: Icon, ...item }) => {
                  const active =
                    href === "/"
                      ? pathname === href
                      : pathname.startsWith(href);
                  return (
                    <Link
                      key={href}
                      className={`studio-nav-item ${
                        "secondary" in item && item.secondary
                          ? "mobile-secondary"
                          : ""
                      } ${active ? "active" : ""}`}
                      href={href}
                      title={label}
                    >
                      <Icon size={18} />
                      <span className="desktop-nav-label">{label}</span>
                      <span className="mobile-nav-label">{mobileLabel}</span>
                    </Link>
                  );
                },
              )}
            </div>
          </div>
        ))}
      </nav>

      <button
        type="button"
        className={`studio-mobile-more ${
          secondaryItems.some((item) => pathname.startsWith(String(item.href)))
            ? "active"
            : ""
        }`}
        aria-label="更多导航"
        aria-expanded={moreOpen}
        onClick={() => setMoreOpen((current) => !current)}
      >
        <MoreHorizontal size={19} />
        <span>更多</span>
      </button>
      {moreOpen && (
        <div className="studio-mobile-more-menu">
          {secondaryItems.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} onClick={() => setMoreOpen(false)}>
              <Icon size={18} />
              <span>{label}</span>
            </Link>
          ))}
        </div>
      )}

      <div className="studio-theme-switch">
        <span>界面主题</span>
        <div role="group" aria-label="界面主题">
          <button
            className={theme === "light" ? "active" : ""}
            type="button"
            aria-pressed={theme === "light"}
            title="浅色主题"
            onClick={() => setTheme("light")}
          >
            <Sun size={14} />
          </button>
          <button
            className={theme === "dark" ? "active" : ""}
            type="button"
            aria-pressed={theme === "dark"}
            title="深色主题"
            onClick={() => setTheme("dark")}
          >
            <Moon size={14} />
          </button>
        </div>
      </div>

      <div className="studio-sidebar-footer">
        <span className={`connection-dot ${connected ? "online" : ""}`} />
        <div>
          <strong>{connected ? "本地 Codex 已连接" : "Codex 未连接"}</strong>
          <small>本机 App Server</small>
        </div>
      </div>
    </aside>
  );
}
