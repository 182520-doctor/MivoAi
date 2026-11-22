"use client";

import { Bot, Menu, Plus } from "lucide-react";
import { useState } from "react";
import { ChatComposer } from "../../features/chat/components/chat-composer";
import type { AgentTask } from "../../features/chat/components/chat-composer";
import { ConversationSidebar } from "../../features/chat/components/conversation-sidebar";
import { MessageList } from "../../features/chat/components/message-list";
import { useConversation } from "../../features/chat/hooks/use-conversation";
import { useDirectorWorkflow } from "../../features/creative-projects/hooks/use-director-workflow";
import { InspirationView } from "../../features/inspiration/components/inspiration-view";
import { ModelSettings } from "../../features/models/components/model-settings";
import { useModelSettings } from "../../features/models/hooks/use-model-settings";
import { useBackendHealth } from "../../features/system/hooks/use-backend-health";
import { NavigationRail } from "./navigation-rail";

export function ChatWorkspace() {
  const chat = useConversation();
  const models = useModelSettings();
  const connected = useBackendHealth();
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [creativeProjectId, setCreativeProjectId] = useState<string | null>(null);
  const [agentTask, setAgentTask] = useState<AgentTask>("chat");
  const [chapterCount, setChapterCount] = useState(6);
  const [targetWords, setTargetWords] = useState(6000);
  const selected = models.selectedModel;
  const director = useDirectorWorkflow(async (prompt, projectId) => {
    setCreativeProjectId(projectId);
    await chat.sendMessage(
      prompt,
      selected ?? { id: "codex-local-default", providerId: "codex_local" },
      projectId,
    );
  });
  const canSend =
    !chat.loading &&
    !models.loading &&
    !director.loading &&
    (selected?.providerId === "volcengine"
      ? selected.configured && selected.integrationStatus === "ready"
      : connected);

  function newConversation() {
    if (chat.isSending) return;
    chat.newConversation();
    setInput("");
    setCreativeProjectId(null);
    setSidebarOpen(false);
  }
  function send() {
    if (!input.trim() || !canSend || chat.isSending) return;
    if (agentTask === "script" && !creativeProjectId) {
      const idea = input;
      setInput("");
      void director.createNovelProject({
        idea,
        chapterCount,
        targetWords,
        sessionId: chat.conversationId,
      });
      return;
    }
    void chat.sendMessage(
      input,
      selected ?? { id: "codex-local-default", providerId: "codex_local" },
      creativeProjectId,
    );
    setInput("");
  }
  const composer = (
    <ChatComposer
      compact={chat.messages.length > 0}
      value={input}
      models={models.models}
      selectedModelId={models.selectedId}
      agentTask={agentTask}
      chapterCount={chapterCount}
      targetWords={targetWords}
      canSend={canSend}
      sending={chat.isSending}
      onChange={setInput}
      onSend={send}
      onStop={chat.interrupt}
      onSettings={() => setSettingsOpen(true)}
      onModelChange={(id) => void models.selectModel(id)}
      onAgentTaskChange={setAgentTask}
      onChapterCountChange={setChapterCount}
      onTargetWordsChange={setTargetWords}
    />
  );

  return (
    <main className="app-shell">
      <NavigationRail
        connected={connected}
        busy={chat.isSending}
        onNew={newConversation}
        onHistory={() => setSidebarOpen(true)}
        onCreate={() => setInput("帮我构思一个新的创意项目")}
      />
      <ConversationSidebar
        open={sidebarOpen}
        busy={chat.isSending}
        loading={chat.loading}
        conversations={chat.conversations}
        selectedId={chat.conversationId}
        connection={chat.connection}
        onClose={() => setSidebarOpen(false)}
        onNew={newConversation}
        onReconnect={() => void chat.reconnect()}
        onSelect={(id) => {
          setSidebarOpen(false);
          void chat.selectConversation(id);
        }}
      />
      <ModelSettings
        open={settingsOpen}
        models={models.models}
        selectedId={models.selectedId}
        loading={models.loading}
        saving={models.saving}
        notice={models.notice}
        disabled={chat.isSending}
        onClose={() => setSettingsOpen(false)}
        onSelect={models.selectModel}
        onSaveKey={models.saveKey}
      />
      <section
        className={`workspace ${chat.messages.length ? "chat-mode" : "home-mode"}`}
      >
        {chat.messages.length === 0 ? (
          <InspirationView
            connected={connected}
            composer={composer}
            notice={director.notice || chat.notice}
            onMenu={() => setSidebarOpen(true)}
            onPrompt={setInput}
          />
        ) : (
          <>
            <header className="chat-header">
              <div>
                <button
                  className="mobile-menu"
                  type="button"
                  title="打开导航"
                  onClick={() => setSidebarOpen(true)}
                >
                  <Menu size={20} />
                </button>
                <span className="chat-mark">
                  <Bot size={17} />
                </span>
                <div>
                  <h1>创意 Agent</h1>
                  <small>与 Codex 一起完善你的想法</small>
                </div>
              </div>
              <button
                className="header-new"
                type="button"
                disabled={chat.isSending}
                onClick={newConversation}
              >
                <Plus size={16} />
                新对话
              </button>
            </header>
            <MessageList
              key={chat.conversationId}
              messages={chat.messages}
              hasMore={Boolean(chat.cursor)}
              loading={chat.loading}
              onLoadMore={() => {
                if (chat.conversationId)
                  void chat.selectConversation(
                    chat.conversationId,
                    chat.cursor,
                  );
              }}
            />
            <div className="composer-dock">
              {chat.notice && (
                <p className="notice" role="alert">
                  {chat.notice}
                </p>
              )}
              {composer}
              <p>Agent 可能会犯错，请核对重要信息</p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
