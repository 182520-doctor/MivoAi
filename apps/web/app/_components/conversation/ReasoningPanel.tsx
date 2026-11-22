import { ChevronDown } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../../_features/chat/types";

type ReasoningPanelProps = {
  message: ChatMessage;
  onToggle: () => void;
};

export function ReasoningPanel({ message, onToggle }: ReasoningPanelProps) {
  if (
    message.role !== "assistant" ||
    (!message.reasoning && !message.reasoningTokens)
  ) {
    return null;
  }
  const tokenText = message.reasoningTokens
    ? ` · ${message.reasoningTokens} reasoning tokens`
    : "";
  return (
    <div className={`reasoning-panel ${message.reasoningOpen ? "open" : ""}`}>
      <button type="button" onClick={onToggle}>
        <ChevronDown size={14} />
        <span>
          {message.status === "streaming" ? "正在思考" : "思考过程"}
          {tokenText}
        </span>
      </button>
      {message.reasoningOpen && (
        <div className="reasoning-body">
          <Markdown remarkPlugins={[remarkGfm]}>
            {message.reasoning ||
              "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。"}
          </Markdown>
        </div>
      )}
    </div>
  );
}
