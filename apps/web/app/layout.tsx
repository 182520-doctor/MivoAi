import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "造境 - Codex 创意 Agent",
  description: "连接本地 Codex App Server 的创意沟通网站",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
