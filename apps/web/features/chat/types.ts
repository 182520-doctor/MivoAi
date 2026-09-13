export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "streaming" | "done" | "error";
  reasoning?: string;
  reasoningTokens?: number;
};

export type Conversation = { id: string; title: string; status?: string };
export type ConversationHistory = {
  messages: Message[];
  cursor: string | null;
  active: boolean;
};
export type MessagePayload = {
  message: string;
  clientMessageId: string;
  providerId: string;
  modelId: string;
};

type Correlation = { clientMessageId?: string };
export type ServerEvent = Correlation &
  (
    | { type: "ready"; conversationId: string }
    | { type: "pong" }
    | {
        type: "meta";
        assistantMessageId?: string;
        threadId?: string;
        turnId?: string;
      }
    | { type: "output"; content: string; reasoning: string }
    | {
        type: "reasoning_started" | "reasoning_delta" | "reasoning_completed";
        text?: string;
      }
    | { type: "reasoning_usage"; tokens: number }
    | { type: "delta" | "message_completed"; text: string }
    | { type: "done"; status: string }
    | { type: "error" | "control_error"; message: string; code?: number }
  );

export type ConnectionStatus = "disconnected" | "connecting" | "connected";
