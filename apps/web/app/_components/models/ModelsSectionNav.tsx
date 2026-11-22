"use client";

import { Cpu, Network, Workflow } from "lucide-react";
import Link from "next/link";

const sections = [
  { href: "/models", label: "模型目录", icon: Cpu },
  { href: "/models/workflows", label: "ComfyUI 工作流", icon: Workflow },
  { href: "/models/connections", label: "连接与测试", icon: Network },
] as const;

export function ModelsSectionNav({
  active,
}: {
  active: "catalog" | "workflows" | "connections";
}) {
  return (
    <nav className="models-section-nav" aria-label="模型中心分区">
      {sections.map(({ href, label, icon: Icon }) => {
        const isActive =
          (active === "catalog" && href === "/models") ||
          (active === "workflows" && href === "/models/workflows") ||
          (active === "connections" && href === "/models/connections");
        return (
          <Link
            key={href}
            href={href}
            className={isActive ? "active" : ""}
            aria-current={isActive ? "page" : undefined}
          >
            <Icon size={17} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
