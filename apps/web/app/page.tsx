import {
  ArrowRight,
  Clapperboard,
  Image as ImageIcon,
  Layers3,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="dashboard-page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">工作台总览</span>
          <h1>先选工作台，再开始创作</h1>
          <p>
            造境包含两个独立但共享底层能力的生产方向。每个入口都对应明确的任务、
            资产和后续操作。
          </p>
        </div>
        <div className="heading-status">
          <span className="status-chip ready">ComfyUI 已接入</span>
          <span className="status-chip ready">短剧可导出 MP4</span>
        </div>
      </header>

      <section className="workspace-cards" aria-label="选择工作台">
        <Link className="workspace-card media" href="/media">
          <div className="workspace-card-top">
            <span className="workspace-card-icon">
              <ImageIcon size={24} />
            </span>
            <span className="workspace-badge">核心方向 01</span>
          </div>
          <div>
            <span className="workspace-kicker">自然语言驱动的媒体生产</span>
            <h2>多模态创作工作台</h2>
            <p>
              用 Agent 生成和编辑图片、视频、音频，集中管理提示词、候选结果、
              工作流版本和生产任务。
            </p>
          </div>
          <div className="workspace-card-tags">
            <span>图片生成</span>
            <span>参考生视频</span>
            <span>图片放大</span>
            <span>60fps 补帧</span>
          </div>
          <div className="workspace-card-footer">
            <span>图片、视频、后处理与任务链路已接通</span>
            <strong>
              进入创作台 <ArrowRight size={16} />
            </strong>
          </div>
        </Link>

        <Link className="workspace-card drama" href="/drama">
          <div className="workspace-card-top">
            <span className="workspace-card-icon">
              <Clapperboard size={24} />
            </span>
            <span className="workspace-badge">核心方向 02</span>
          </div>
          <div>
            <span className="workspace-kicker">从故事到成片的完整流水线</span>
            <h2>短剧制作工作台</h2>
            <p>
              组织故事设定、剧本、镜头拆解、角色资产生成、分镜视频、配音、
              字幕和整集合成。
            </p>
          </div>
          <div className="workspace-card-tags">
            <span>剧本版本</span>
            <span>资产与分镜</span>
            <span>TTS 与字幕</span>
            <span>整集合成</span>
          </div>
          <div className="workspace-card-footer">
            <span>已可生成镜头视频与整集 MP4</span>
            <strong>
              查看制作流程 <ArrowRight size={16} />
            </strong>
          </div>
        </Link>
      </section>

      <section className="dashboard-lower">
        <Link className="agent-entry-card" href="/chat">
          <span className="agent-entry-icon">
            <MessageSquareText size={21} />
          </span>
          <div>
            <span className="eyebrow">Agent 工作台</span>
            <h3>和 Agent 先梳理创意</h3>
            <p>继续使用本地 Codex，支持流式回复、思考过程和会话历史。</p>
          </div>
          <ArrowRight size={18} />
        </Link>

        <div className="capability-map">
          <div className="capability-map-head">
            <Layers3 size={18} />
            <strong>两个工作台共享的底座</strong>
          </div>
          <div className="capability-map-grid">
            <span>本地 Codex Agent</span>
            <span>统一生成任务</span>
            <span>素材版本库</span>
            <span>Workflow / Provider</span>
            <span>短剧领域模型</span>
            <span>审批与生产记录</span>
          </div>
          <p>
            <Sparkles size={14} />
            当前已打通剧本、资产、关键帧、镜头视频、配音、字幕、后处理与整集成片。
          </p>
        </div>
      </section>
    </main>
  );
}
