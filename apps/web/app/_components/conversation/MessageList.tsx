import {
  CheckCircle2,
  LoaderCircle,
  Sparkles,
  TriangleAlert,
  Wrench,
} from "lucide-react";
import type { RefObject } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../../_features/chat/types";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";
import { ReasoningPanel } from "./ReasoningPanel";

type MessageListProps = {
  messages: ChatMessage[];
  cursor: string | null;
  bottomRef: RefObject<HTMLDivElement | null>;
  onLoadOlder: () => void;
  onToggleReasoning: (messageId: string) => void;
};

export function MessageList({
  messages,
  cursor,
  bottomRef,
  onLoadOlder,
  onToggleReasoning,
}: MessageListProps) {
  return (
    <div className="message-list">
      {cursor && (
        <button className="load-more" onClick={onLoadOlder}>
          加载更早消息
        </button>
      )}
      {messages.map((message) => (
        <article className={`message ${message.role}`} key={message.id}>
          {message.role === "assistant" && (
            <div className="avatar">
              <Sparkles size={15} />
            </div>
          )}
          <div className="message-content">
            {message.role === "assistant" && (
              <span className="message-author">造境 Agent</span>
            )}
            <ReasoningPanel
              message={message}
              onToggle={() => onToggleReasoning(message.id)}
            />
            {message.role === "assistant" && message.toolCalls?.length ? (
              <div className="message-tool-calls">
                {message.toolCalls.map((call) => (
                  <details
                    className={`message-tool-call ${call.status}`}
                    key={call.id}
                  >
                    <summary>
                      {call.status === "running" ? (
                        <LoaderCircle className="spin" size={14} />
                      ) : call.status === "failed" ? (
                        <TriangleAlert size={14} />
                      ) : (
                        <CheckCircle2 size={14} />
                      )}
                      <Wrench size={14} />
                      <span>{toolName(call.name)}</span>
                      <small>
                        {call.status === "running"
                          ? "执行中"
                          : call.status === "failed"
                            ? "失败"
                            : call.durationMs
                              ? `${(call.durationMs / 1000).toFixed(1)} 秒`
                              : "已完成"}
                      </small>
                    </summary>
                    {call.arguments && (
                      <pre>{JSON.stringify(call.arguments, null, 2)}</pre>
                    )}
                    {call.result && <pre>{formatToolResult(call.result)}</pre>}
                  </details>
                ))}
              </div>
            ) : null}
            <div className="markdown">
              <Markdown
                remarkPlugins={[remarkGfm]}
                components={{
                  img: ({ src, alt }) =>
                    typeof src === "string" ? (
                      <a
                        className="message-image-link"
                        href={backendResourceUrl(src)}
                        target="_blank"
                        rel="noreferrer"
                        title="打开原图"
                      >
                        <img
                          className="message-image"
                          src={backendResourceUrl(src)}
                          alt={alt ?? "Agent 生成图片"}
                          loading="lazy"
                        />
                      </a>
                    ) : null,
                }}
              >
                {message.content || "正在生成回复…"}
              </Markdown>
            </div>
            {message.role === "assistant" &&
              message.status === "streaming" && (
                <span className="typing-dot" />
              )}
            {message.status === "done" && (
              <span className="message-status">
                <CheckCircle2 size={13} />
                由本地 Codex 生成
              </span>
            )}
            {message.status === "interrupted" && (
              <span className="message-interrupted">
                <TriangleAlert size={13} />
                回复被服务重启中断，可重新发送
              </span>
            )}
            {message.status === "error" && (
              <span className="message-error">连接出现问题</span>
            )}
          </div>
        </article>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function toolName(name: string) {
  return {
    zaojing_discover_media_models: "发现可用媒体模型",
    zaojing_list_media_assets: "查询参考素材",
    zaojing_generate_media: "提交多模态生成",
    zaojing_get_media_task: "等待生成结果",
  }[name] ?? name;
}

function formatToolResult(value: string) {
  try {
    const parsed = JSON.parse(value);
    const task = parsed.task ?? parsed.data ?? parsed;
    if (task?.status) {
      return JSON.stringify(
        {
          status: task.status,
          taskId: task.id,
          model: task.modelName,
          resultUrls: task.resultUrls,
          error: task.errorMessage,
        },
        null,
        2,
      );
    }
    if (task?.models) {
      return JSON.stringify(
        task.models.map(
          (model: {
            id: string;
            name: string;
            capabilities?: string[];
          }) => ({
            id: model.id,
            name: model.name,
            capabilities: model.capabilities,
          }),
        ),
        null,
        2,
      );
    }
  } catch {
    // Show raw text from non-JSON tools.
  }
  return value.length > 1200 ? `${value.slice(0, 1200)}…` : value;
}
