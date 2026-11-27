import {
  ArrowUp,
  History,
  Image as ImageIcon,
  Lightbulb,
  Menu,
  Search,
  Video,
  WandSparkles,
} from "lucide-react";
import { Composer } from "../conversation/Composer";

const quickActions = [
  {
    icon: Lightbulb,
    title: "创意策划",
    detail: "把模糊灵感变成清晰方案",
    prompt: "帮我把一个模糊的创意整理成清晰方案",
  },
  {
    icon: ImageIcon,
    title: "画面提示词",
    detail: "设计构图、风格与光影",
    prompt: "为一张产品海报设计画面和提示词",
  },
  {
    icon: Video,
    title: "短片故事",
    detail: "从故事梗概到分镜节奏",
    prompt: "和我一起头脑风暴一个短片故事",
  },
  {
    icon: WandSparkles,
    title: "灵感扩写",
    detail: "延展更多可执行的方向",
    prompt: "请基于我的想法延展三个不同的创意方向",
  },
];

const galleryItems = [
  {
    className: "art-one",
    label: "雪山叙事",
    prompt: "帮我构思一个发生在雪山中的电影感故事",
  },
  {
    className: "art-two",
    label: "玻璃花语",
    prompt: "设计一组透明玻璃花的视觉概念",
  },
  {
    className: "art-three",
    label: "太空伙伴",
    prompt: "构思一个猫咪宇航员的短片创意",
  },
  {
    className: "art-four",
    label: "未来绿洲",
    prompt: "设计一个未来生态城市的世界观",
  },
];

type HomeViewProps = {
  connected: boolean;
  notice: string;
  input: string;
  selectedModelName: string;
  isSending: boolean;
  canSend: boolean;
  onChangeInput: (value: string) => void;
  onOpenHistory: () => void;
  onOpenSettings: () => void;
  onSend: () => void;
  onStop: () => void;
  onPrompt: (prompt: string) => void;
};

export function HomeView({
  connected,
  notice,
  input,
  selectedModelName,
  isSending,
  canSend,
  onChangeInput,
  onOpenHistory,
  onOpenSettings,
  onSend,
  onStop,
  onPrompt,
}: HomeViewProps) {
  return (
    <div className="home-scroll">
      <header className="home-header">
        <button
          className="mobile-menu"
          type="button"
          title="打开导航"
          onClick={onOpenHistory}
        >
          <Menu size={21} />
        </button>
        <button className="home-history" type="button" onClick={onOpenHistory}>
          <History size={17} />
          历史会话
        </button>
        <span className={`server-state ${connected ? "online" : ""}`}>
          <i />
          {connected ? "Codex 已连接" : "等待连接"}
        </span>
      </header>
      <section className="creation-zone">
        <div className="creation-intro">
          <span className="creation-index">AGENT STUDIO / 创意起点</span>
          <h1>
            从一句想法开始，
            <em>把创意做成作品。</em>
          </h1>
          <p>
            描述你的目标、画面或故事。Agent 会先把方向梳理清楚，再衔接图片、
            视频与短剧生产。
          </p>
        </div>
        <Composer
          input={input}
          selectedModelName={selectedModelName}
          isSending={isSending}
          canSend={canSend}
          onChangeInput={onChangeInput}
          onOpenSettings={onOpenSettings}
          onSend={onSend}
          onStop={onStop}
        />
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
            <button type="button">技能</button>
            <button type="button">短片</button>
            <button type="button">灵感</button>
          </div>
          <label>
            <Search size={17} />
            <input aria-label="搜索灵感" placeholder="搜索创意灵感" />
          </label>
        </div>
        <div className="discover-intro">
          <span>最近的视觉方向</span>
          <small>选择一张灵感卡片，继续和 Agent 展开</small>
        </div>
        <div className="gallery">
          {galleryItems.map((item) => (
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
        </div>
      </section>
    </div>
  );
}
