"use client";

import {
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clapperboard,
  FolderTree,
  ListChecks,
  MessageSquarePlus,
  Radio,
  ScanSearch,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useEffect, useRef } from "react";
import { useChatSession } from "../../_features/chat/useChatSession";
import { useHealthStatus } from "../../_features/health/useHealthStatus";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { Composer } from "../conversation/Composer";
import { MessageList } from "../conversation/MessageList";

type DramaAgentPanelProps = {
  projectId: string;
  projectTitle: string;
  episodeId: string | null;
  stageId: string;
  scope: "global" | "episode" | "stage";
  scopeLabel: string;
  stageLabel: string;
  threadKey: string;
  externalPrompt: string;
  onPromptConsumed: () => void;
  onWorkspaceChanged: () => void;
};

export function DramaAgentPanel({
  projectId,
  projectTitle,
  episodeId,
  stageId,
  scope,
  scopeLabel,
  stageLabel,
  threadKey,
  externalPrompt,
  onPromptConsumed,
  onWorkspaceChanged,
}: DramaAgentPanelProps) {
  const { connected } = useHealthStatus();
  const modelSettings = useModelSettings();
  const chat = useChatSession({
    selectedModel: modelSettings.selectedModel,
    onConversationsChanged: async () => undefined,
    storageKey: threadKey,
    initialPromptFromUrl: false,
    newConversationContext: {
      projectId,
      episodeId,
      scope,
    },
  });
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const observedToolsRef = useRef(new Set<string>());
  const canSend = modelSettings.canUseSelectedModel(connected);
  const quickPrompts = [
    {
      icon: ListChecks,
      title: "梳理当前进度",
      description: "总结已完成内容与下一步重点",
      prompt:
        "请基于当前项目上下文，梳理已完成的内容、仍未解决的问题，以及最有价值的下一步。",
    },
    {
      icon: ScanSearch,
      title: "检查内容一致性",
      description: "核对剧本、分镜和制作资产",
      prompt:
        "请检查当前范围内剧本、分镜和制作资产的一致性，列出具体冲突，并给出可执行的修正建议。",
    },
    {
      icon: WandSparkles,
      title: `推进「${stageLabel}」`,
      description: "Agent 完成专业草稿并自审后交由你审核",
      prompt: `请直接推进当前阶段「${stageLabel}」和范围「${scopeLabel}」。读取真实状态与角色手册，完成专业草稿，按角色清单自审并修复明显问题，然后给我一份可审核的交付物和关键取舍摘要。不要要求我逐项填写专业内容。`,
    },
  ];
  const scopeContext = [
    "【短剧工作台上下文】",
    `项目：${projectTitle}`,
    `项目 ID：${projectId}`,
    `当前范围：${scopeLabel}`,
    `当前阶段：${stageLabel}（${stageId}）`,
    episodeId ? `当前分集 ID：${episodeId}` : "当前范围不限定单一分集",
    episodeId
      ? "单集操作优先调用 zaojing_get_drama_episode，只读取当前分集。"
      : "",
    episodeId
      ? "修改单集计划或镜头后调用 zaojing_audit_drama_episode，修复错误后再请求用户确认。"
      : "",
    stageId === "script"
      ? "提交剧本审批前调用 zaojing_audit_drama_script，修复分集、场次、对白和占位符问题。"
      : "",
    "AI 主导原则：除首次创意方向和内容边界外，你负责编剧、表演、角色、场景、分镜和视频的专业执行；我主要做审核、否决或要求重做。只在重大不可逆分歧、内容边界、版权、成本或我明确否决时停下来集中提问。",
    "请使用造境短剧工具读取和修改真实状态；需要昂贵生成或阶段放行时先向用户确认。",
  ]
    .filter(Boolean)
    .join("\n");

  useEffect(() => {
    if (!externalPrompt.trim()) return;
    chat.setInput(externalPrompt);
    onPromptConsumed();
    // A prompt is injected once per explicit canvas action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalPrompt]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat.messages]);

  useEffect(() => {
    const mutatingTools = new Set([
      "zaojing_generate_media",
      "zaojing_synthesize_speech",
      "zaojing_process_media",
      "zaojing_save_drama_draft",
      "zaojing_plan_drama_episodes",
      "zaojing_plan_drama_shots",
      "zaojing_plan_drama_assets",
      "zaojing_bind_drama_asset",
      "zaojing_update_drama_asset_candidate",
      "zaojing_create_drama_production_run",
      "zaojing_plan_drama_production_run",
      "zaojing_start_drama_production_run",
      "zaojing_retry_drama_production_failures",
      "zaojing_cancel_drama_production_run",
      "zaojing_review_drama_stage",
      "zaojing_retry_media_tasks",
      "zaojing_render_episode",
    ]);
    let changed = false;
    for (const message of chat.messages) {
      for (const call of message.toolCalls ?? []) {
        if (
          call.status === "completed" &&
          mutatingTools.has(call.name) &&
          !observedToolsRef.current.has(call.id)
        ) {
          observedToolsRef.current.add(call.id);
          changed = true;
        }
      }
    }
    if (changed) onWorkspaceChanged();
  }, [chat.messages, onWorkspaceChanged]);

  return (
    <aside className="drama-agent-panel" aria-label="短剧 Agent 对话">
      <header className="drama-agent-panel-head">
        <div>
          <span>
            <Bot size={16} />
          </span>
          <div title={projectTitle}>
            <div className="drama-agent-title-line">
              <strong>造境 Agent</strong>
              <span>CREATIVE COPILOT</span>
            </div>
            <small>{projectTitle}</small>
          </div>
        </div>
        <div>
          <em className={chat.isSending ? "busy" : connected ? "ready" : ""}>
            <Radio size={11} />
            {chat.isSending ? "执行中" : connected ? "已连接" : "未连接"}
          </em>
          <button
            type="button"
            title="为当前范围创建新对话"
            disabled={chat.isSending}
            onClick={chat.newConversation}
          >
            <MessageSquarePlus size={14} />
          </button>
        </div>
      </header>

      <div className="drama-agent-context">
        <span title={scopeLabel}>
          <FolderTree size={12} />
          {scopeLabel}
        </span>
        <span title={stageLabel}>
          <Clapperboard size={12} />
          {stageLabel}
        </span>
        <small>
          {chat.conversationId
            ? `Thread ${chat.conversationId.slice(0, 8)}`
            : "首条消息后创建独立对话"}
        </small>
      </div>

      <div className="drama-agent-conversation">
        {chat.messages.length ? (
          <MessageList
            messages={chat.messages}
            cursor={chat.cursor}
            bottomRef={bottomRef}
            onLoadOlder={() =>
              chat.conversationId
                ? void chat.selectConversation(chat.conversationId, true)
                : undefined
            }
            onToggleReasoning={chat.toggleReasoning}
          />
        ) : (
          <div className="drama-agent-empty">
            <div className="drama-agent-empty-mark">
              <span>
                <Sparkles size={24} />
              </span>
            </div>
            <em className="drama-agent-context-ready">
              <CheckCircle2 size={13} />
              范围上下文已就绪
            </em>
            <strong>把下一步交给 Agent</strong>
            <p>
              它会读取当前项目、分集与阶段状态，再选择规划、生成或审核工具。
            </p>
            <div className="drama-agent-suggestions">
              <div>
                <span>推荐下一步</span>
                <small>点击填入指令</small>
              </div>
              {quickPrompts.map((suggestion) => {
                const SuggestionIcon = suggestion.icon;
                return (
                  <button
                    key={suggestion.title}
                    type="button"
                    onClick={() => chat.setInput(suggestion.prompt)}
                  >
                    <span>
                      <SuggestionIcon size={15} />
                    </span>
                    <div>
                      <strong>{suggestion.title}</strong>
                      <small>{suggestion.description}</small>
                    </div>
                    <ArrowUpRight size={14} />
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="drama-agent-compose">
        {chat.notice && <p className="notice">{chat.notice}</p>}
        <div className="drama-agent-composer-head">
          <span>
            <Sparkles size={12} /> Agent 指令
          </span>
          <small>Enter 发送 · Shift + Enter 换行</small>
        </div>
        <Composer
          compact
          input={chat.input}
          placeholder="告诉 Agent 下一步要完成什么…"
          selectedModelName={
            modelSettings.selectedModel?.name ?? "本地 Codex Agent"
          }
          isSending={chat.isSending}
          canSend={canSend}
          allowModelSettings={false}
          onChangeInput={chat.setInput}
          onOpenSettings={() => undefined}
          onSend={() => void chat.sendMessage(chat.input, scopeContext)}
          onStop={() => void chat.stopReply()}
        />
      </div>
    </aside>
  );
}
