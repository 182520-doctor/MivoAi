import {
  ArrowUp,
  Bot,
  ChevronDown,
  CircleStop,
  Ratio,
  Settings2,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";

type ComposerProps = {
  compact?: boolean;
  input: string;
  placeholder?: string;
  selectedModelName: string;
  isSending: boolean;
  canSend: boolean;
  allowModelSettings?: boolean;
  onChangeInput: (value: string) => void;
  onOpenSettings: () => void;
  onSend: () => void;
  onStop: () => void;
};

export function Composer({
  compact = false,
  input,
  placeholder = "输入你的创意，和 Agent 一起把它变清晰…",
  selectedModelName,
  isSending,
  canSend,
  allowModelSettings = true,
  onChangeInput,
  onOpenSettings,
  onSend,
  onStop,
}: ComposerProps) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSend();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <form
      className={`composer ${compact ? "compact" : "studio"}`}
      onSubmit={submit}
    >
      <textarea
        aria-label="发送消息"
        value={input}
        onChange={(event) => onChangeInput(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={compact ? 2 : 4}
      />
      <div className="composer-footer">
        <div className="composer-tools">
          {allowModelSettings ? (
            <>
              <button
                type="button"
                className="tool-pill primary"
                onClick={onOpenSettings}
              >
                <Bot size={17} />
                {selectedModelName}
                <ChevronDown size={14} />
              </button>
              <button
                type="button"
                className="tool-pill icon-only"
                title="模型与偏好设置"
                onClick={onOpenSettings}
              >
                <Settings2 size={17} />
              </button>
            </>
          ) : (
            <span className="tool-pill primary">
              <Bot size={17} />
              {selectedModelName}
            </span>
          )}
          {!compact && (
            <button
              type="button"
              className="tool-pill"
              onClick={() => onChangeInput("请帮我完善这个创意的执行方案：")}
            >
              <WandSparkles size={16} />
              创意策划
            </button>
          )}
          {!compact && (
            <button
              type="button"
              className="tool-pill icon-only"
              title="画面比例"
            >
              <Ratio size={17} />
            </button>
          )}
        </div>
        <div className="submit-area">
          {!compact && (
            <span>
              <Sparkles size={14} /> 本地 Codex
            </span>
          )}
          {isSending ? (
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
              disabled={!input.trim() || !canSend}
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
