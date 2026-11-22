import {
  FolderOpen,
  History,
  Home,
  LayoutGrid,
  Sparkles,
  WandSparkles,
} from "lucide-react";

type Props = {
  connected: boolean;
  busy: boolean;
  onNew: () => void;
  onHistory: () => void;
  onCreate: () => void;
};
export function NavigationRail({
  connected,
  busy,
  onNew,
  onHistory,
  onCreate,
}: Props) {
  return (
    <aside className="rail" aria-label="主导航">
      <button
        className="logo-button"
        type="button"
        title="造境"
        disabled={busy}
        onClick={onNew}
      >
        <Sparkles size={25} />
      </button>
      <nav>
        <button
          className="rail-item active"
          type="button"
          disabled={busy}
          onClick={onNew}
        >
          <Home size={21} />
          <span>灵感</span>
        </button>
        <button className="rail-item" type="button" onClick={onCreate}>
          <WandSparkles size={21} />
          <span>创作</span>
        </button>
        <button className="rail-item" type="button" onClick={onHistory}>
          <History size={21} />
          <span>对话</span>
        </button>
        <button className="rail-item" type="button" disabled title="暂未开放">
          <FolderOpen size={21} />
          <span>资产</span>
        </button>
        <button className="rail-item" type="button" disabled title="暂未开放">
          <LayoutGrid size={21} />
          <span>画布</span>
        </button>
      </nav>
      <div className="rail-spacer" />
      <span
        className={`rail-status ${connected ? "online" : ""}`}
        title={connected ? "Codex 已连接" : "Codex 未连接"}
      />
    </aside>
  );
}
