import type { Metadata } from "next";
import "./globals.css";
import "./theme.css";
import "./drama-workspace.css";
import "./studio-ui.css";
import { StudioFrame } from "./_components/shell/StudioFrame";

export const metadata: Metadata = {
  title: "造境 - Codex 创意 Agent",
  description: "连接本地 Codex App Server 的创意沟通网站",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <StudioFrame>{children}</StudioFrame>
      </body>
    </html>
  );
}
