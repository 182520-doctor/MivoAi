"use client";

import { ArrowUp, Menu, Search } from "lucide-react";
import { useState, type ReactNode } from "react";
import { galleryItems, quickActions } from "../data/prompts";

type Props = {
  connected: boolean;
  composer: ReactNode;
  notice: string;
  onMenu: () => void;
  onPrompt: (prompt: string) => void;
};
export function InspirationView({
  connected,
  composer,
  notice,
  onMenu,
  onPrompt,
}: Props) {
  const [query, setQuery] = useState("");
  const items = galleryItems.filter((item) =>
    `${item.label} ${item.prompt}`.includes(query.trim()),
  );
  return (
    <div className="home-scroll">
      <header className="home-header">
        <button
          className="mobile-menu"
          type="button"
          title="打开导航"
          onClick={onMenu}
        >
          <Menu size={21} />
        </button>
        <span className={`server-state ${connected ? "online" : ""}`}>
          <i />
          {connected ? "Codex 已连接" : "等待连接"}
        </span>
      </header>
      <section className="creation-zone">
        <h1>
          开启你的 <em>Agent 创作</em>，即刻造梦！
        </h1>
        {composer}
        {notice && (
          <p className="notice" role="alert">
            {notice}
          </p>
        )}
        <div className="quick-actions">
          {quickActions.map(({ icon: Icon, title, detail, prompt }, index) => (
            <button key={title} type="button" onClick={() => onPrompt(prompt)}>
              <span className={`quick-icon tone-${index + 1}`}>
                <Icon size={20} />
              </span>
              <span>
                <strong>{title}</strong>
                <small>{detail}</small>
              </span>
              <ArrowUp size={16} />
            </button>
          ))}
        </div>
      </section>
      <section className="discover">
        <div className="discover-head">
          <div className="discover-tabs">
            <button className="active" type="button">
              发现
            </button>
          </div>
          <label>
            <Search size={17} />
            <input
              aria-label="搜索灵感"
              placeholder="搜索创意灵感"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </div>
        <div className="gallery">
          {items.map((item) => (
            <button
              className="gallery-item"
              type="button"
              key={item.label}
              onClick={() => onPrompt(item.prompt)}
            >
              <span className={`gallery-art ${item.className}`} />
              <span className="gallery-label">
                <strong>{item.label}</strong>
                <small>用 Agent 继续创作</small>
              </span>
            </button>
          ))}
          {items.length === 0 && <p>暂无匹配的灵感</p>}
        </div>
      </section>
    </div>
  );
}
