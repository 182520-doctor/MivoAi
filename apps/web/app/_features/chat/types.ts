export type MessageStatus = "streaming" | "done" | "interrupted" | "error";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: MessageStatus;
  reasoning?: string;
  reasoningTokens?: number;
  reasoningOpen?: boolean;
  toolCalls?: ChatToolCall[];
};

export type ChatToolCall = {
  id: string;
  name: string;
  status: "running" | "completed" | "failed";
  arguments?: Record<string, unknown>;
  result?: string;
  durationMs?: number;
};

export type ServerEvent = {
  type:
    | "meta"
    | "reasoning_started"
    | "reasoning_delta"
    | "reasoning_completed"
    | "reasoning_usage"
    | "delta"
    | "message_completed"
    | "tool_started"
    | "tool_completed"
    | "done"
    | "error";
  text?: string;
  message?: string;
  status?: string;
  tokens?: number;
  assistantMessageId?: string;
  toolCallId?: string;
  tool?: string;
  namespace?: string;
  arguments?: Record<string, unknown>;
  contentItems?: Array<{ type?: string; text?: string }>;
  success?: boolean;
  durationMs?: number;
};

export type ConversationSummary = {
  id: string;
  title: string;
  status?: string;
  workspace?: string | null;
  threadId?: string | null;
  messageCount?: number;
  updatedAt?: string | null;
  projectId?: string | null;
  episodeId?: string | null;
  scope?: string | null;
};

export type ConversationHistory = {
  messages: ChatMessage[];
  cursor: string | null;
  active: boolean;
};

export type SendMessageInput = {
  conversationId: string;
  message: string;
  clientMessageId: string;
  providerId: string;
  modelId: string;
  signal: AbortSignal;
};
