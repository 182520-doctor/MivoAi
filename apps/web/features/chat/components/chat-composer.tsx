"use client";

import {
  ArrowUp,
  Bot,
  ChevronDown,
  CircleStop,
  Settings2,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";

type Props = {
  compact?: boolean;
  value: string;
  modelName: string;
  canSend: boolean;
  sending: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onSettings: () => void;
};

export function ChatComposer({
  compact = false,
  value,
  modelName,
  canSend,
  sending,
  onChange,
  onSend,
  onStop,
  onSettings,
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
        placeholder="输入你的创意，和 Agent 一起把它变清晰…"
        rows={compact ? 2 : 4}
      />
      <div className="composer-footer">
        <div className="composer-tools">
          <button
            type="button"
            className="tool-pill primary"
            disabled={sending}
            onClick={onSettings}
          >
            <Bot size={17} />
            {modelName}
            <ChevronDown size={14} />
          </button>
          <button
            type="button"
            className="tool-pill icon-only"
            title="模型与偏好设置"
            onClick={onSettings}
          >
            <Settings2 size={17} />
          </button>
          {!compact && (
            <button
              type="button"
              className="tool-pill"
              onClick={() => onChange("请帮我完善这个创意的执行方案：")}
            >
              <WandSparkles size={16} />
              创意策划
            </button>
          )}
        </div>
        <div className="submit-area">
          {!compact && (
            <span>
              <Sparkles size={14} /> 创意 Agent
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
