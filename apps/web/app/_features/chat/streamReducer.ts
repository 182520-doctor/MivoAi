import type { ChatMessage, ServerEvent } from "./types";

export function applyServerEvent(message: ChatMessage, event: ServerEvent): ChatMessage {
  if (event.type === "meta" && event.assistantMessageId) {
    return { ...message, id: event.assistantMessageId };
  }
  if (event.type === "reasoning_started") {
    return {
      ...message,
      reasoning: event.text || message.reasoning || "正在分析你的需求…",
      reasoningOpen: false,
    };
  }
  if (event.type === "reasoning_delta" && event.text) {
    return {
      ...message,
      reasoning: `${message.reasoning ?? ""}${event.text}`,
      reasoningOpen: false,
    };
  }
  if (event.type === "reasoning_completed") {
    return {
      ...message,
      reasoning:
        event.text ||
        message.reasoning ||
        "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。",
      reasoningOpen: false,
    };
  }
  if (event.type === "reasoning_usage") {
    return {
      ...message,
      reasoningTokens: event.tokens ?? message.reasoningTokens,
      reasoning:
        message.reasoning ||
        (event.tokens && event.tokens > 0
          ? "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。"
          : message.reasoning),
    };
  }
  if (event.type === "tool_started" && event.toolCallId) {
    return {
      ...message,
      toolCalls: [
        ...(message.toolCalls ?? []),
        {
          id: event.toolCallId,
          name: event.tool ?? "media_tool",
          status: "running",
          arguments: event.arguments,
        },
      ],
    };
  }
  if (event.type === "tool_completed" && event.toolCallId) {
    const resultText = (event.contentItems ?? [])
      .filter((item) => item.type === "inputText" && item.text)
      .map((item) => item.text)
      .join("\n");
    const nextStatus = event.success === false ? "failed" : "completed";
    return {
      ...message,
      toolCalls: (message.toolCalls ?? []).map((call) =>
        call.id === event.toolCallId
          ? {
              ...call,
              name: event.tool ?? call.name,
              status: nextStatus,
              arguments: event.arguments ?? call.arguments,
              result: resultText || call.result,
              durationMs: event.durationMs,
            }
          : call,
      ),
    };
  }
  if (event.type === "message_completed") {
    return { ...message, content: event.text ?? message.content };
  }
  if (event.type === "delta" && event.text) {
    return { ...message, content: message.content + event.text };
  }
  if (event.type === "done") {
    return {
      ...message,
      status: event.status === "interrupted" ? "interrupted" : "done",
    };
  }
  return message;
}
