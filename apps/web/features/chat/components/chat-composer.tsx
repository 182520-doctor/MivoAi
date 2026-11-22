"use client";

import {
  ArrowUp,
  ChevronDown,
  CircleStop,
  Cpu,
  Settings2,
  Sparkles,
} from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";

export type AgentTask = "chat" | "script";

type ModelOption = {
  id: string;
  providerName: string;
  name: string;
  capabilities: string[];
};

type Props = {
  compact?: boolean;
  value: string;
  models: ModelOption[];
  selectedModelId: string;
  agentTask: AgentTask;
  chapterCount: number;
  targetWords: number;
  canSend: boolean;
  sending: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onSettings: () => void;
  onModelChange: (id: string) => void;
  onAgentTaskChange: (task: AgentTask) => void;
  onChapterCountChange: (value: number) => void;
  onTargetWordsChange: (value: number) => void;
};

export function ChatComposer({
  compact = false,
  value,
  models,
  selectedModelId,
  agentTask,
  chapterCount,
  targetWords,
  canSend,
  sending,
  onChange,
  onSend,
  onStop,
  onSettings,
  onModelChange,
  onAgentTaskChange,
  onChapterCountChange,
  onTargetWordsChange,
}: Props) {
  function submit(event: FormEvent) {
    event.preventDefault();
    if (canSend && value.trim() && !sending) onSend();
  }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      if (canSend && value.trim() && !sending) onSend();
    }
  }
  return (
    <form
      className={`composer ${compact ? "compact" : "studio"}`}
      onSubmit={submit}
    >
      <textarea
        aria-label="发送消息"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={keyDown}
        placeholder={
          agentTask === "script"
            ? "描述你的故事创意，例如：一只猫为了寻找主人，踏上跨越城市的冒险…"
            : "输入你的创意，和 Agent 一起把它变清晰…"
        }
        rows={compact ? 2 : 4}
      />
      {agentTask === "script" && !compact && (
        <div className="script-options">
          <span>剧本设置</span>
          <label>
            章节
            <input
              type="number"
              min={1}
              max={200}
              value={chapterCount}
              onChange={(event) =>
                onChapterCountChange(Number(event.target.value))
              }
            />
          </label>
          <label>
            目标字数
            <input
              type="number"
              min={500}
              max={300000}
              step={500}
              value={targetWords}
              onChange={(event) =>
                onTargetWordsChange(Number(event.target.value))
              }
            />
          </label>
        </div>
      )}
      <div className="composer-footer">
        <div className="composer-tools">
          <span className="agent-mode-label">
            <Sparkles size={16} />
            Agent 模式
          </span>
          <label className="composer-select task-select">
            <select
              aria-label="Agent 能力"
              value={agentTask}
              disabled={sending || compact}
              onChange={(event) =>
                onAgentTaskChange(event.target.value as AgentTask)
              }
            >
              <option value="chat">自由对话</option>
              <option value="script">生成剧本</option>
            </select>
            <ChevronDown size={14} />
          </label>
          <label className="composer-select model-select">
            <Cpu size={15} />
            <select
              aria-label="选择大模型"
              value={selectedModelId}
              disabled={sending}
              onChange={(event) => onModelChange(event.target.value)}
            >
              {models
                .filter((model) => model.capabilities.includes("text"))
                .map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.providerName} · {model.name}
                  </option>
                ))}
            </select>
            <ChevronDown size={14} />
          </label>
          <button
            type="button"
            className="tool-pill icon-only"
            title="模型与偏好设置"
            onClick={onSettings}
          >
            <Settings2 size={17} />
          </button>
        </div>
        <div className="submit-area">
          {!compact && (
            <span>
              <Sparkles size={14} />
              {agentTask === "script" ? "生成剧本" : "自由对话"}
            </span>
          )}
          {sending ? (
            <button
              className="send-button stop"
              type="button"
              onClick={onStop}
              title="停止回复"
            >
              <CircleStop size={20} />
            </button>
          ) : (
            <button
              className="send-button"
              type="submit"
              disabled={!value.trim() || !canSend}
              title="发送消息"
            >
              <ArrowUp size={20} />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
