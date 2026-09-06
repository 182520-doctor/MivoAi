import type { Message, ServerEvent } from "../types";

export function applyMessageEvent(
  message: Message,
  event: ServerEvent,
): Message {
  switch (event.type) {
    case "meta":
      return { ...message, id: event.assistantMessageId ?? message.id };
    case "output":
      return { ...message, content: event.content, reasoning: event.reasoning };
    case "delta":
      return { ...message, content: message.content + event.text };
    case "message_completed":
      return { ...message, content: event.text };
    case "reasoning_started":
    case "reasoning_completed":
      return { ...message, reasoning: event.text || message.reasoning || "" };
    case "reasoning_delta":
      return {
        ...message,
        reasoning: (message.reasoning ?? "") + (event.text ?? ""),
      };
    case "reasoning_usage":
      return { ...message, reasoningTokens: event.tokens };
    case "done":
      return { ...message, status: "done" };
    case "error":
      return { ...message, status: "error" };
    default:
      return message;
  }
}
