"use client";

import { useState } from "react";
import { useChatSession } from "../../_features/chat/useChatSession";
import { useConversationList } from "../../_features/chat/useConversationList";
import { useHealthStatus } from "../../_features/health/useHealthStatus";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { ChatView } from "../chat/ChatView";
import { HomeView } from "../home/HomeView";
import { AgentContextRail } from "./AgentContextRail";
import { HistoryDrawer } from "./HistoryDrawer";
import { ModelSettingsDrawer } from "./ModelSettingsDrawer";

export function WorkspaceShell() {
  const [historyOpen, setHistoryOpen] = useState(false);
  const { connected } = useHealthStatus();
  const modelSettings = useModelSettings();
  const { conversations, refresh: refreshConversations } = useConversationList();
  const chat = useChatSession({
    selectedModel: modelSettings.selectedModel,
    onConversationsChanged: refreshConversations,
  });

  const canSend = modelSettings.canUseSelectedModel(connected);
  const selectedModelName =
    modelSettings.selectedModel?.name ?? "本地 Codex Agent";
  const activeConversation = conversations.find(
    (conversation) => conversation.id === chat.conversationId,
  );
  const conversationTitle =
    activeConversation?.title ?? "新的创意对话";
  const drawerOpen = historyOpen || modelSettings.settingsOpen;

  function startNewConversation() {
    chat.newConversation();
    setHistoryOpen(false);
  }

  function selectConversation(id: string) {
    setHistoryOpen(false);
    void chat.selectConversation(id);
  }

  return (
    <main className="chat-workspace">
      {drawerOpen && (
        <button
          className="drawer-backdrop"
          type="button"
          aria-label="关闭侧边栏"
          onClick={() => {
            setHistoryOpen(false);
            modelSettings.setSettingsOpen(false);
          }}
        />
      )}

      <ModelSettingsDrawer
        open={modelSettings.settingsOpen}
        models={modelSettings.models}
        selectedModel={modelSettings.selectedModel}
        selectedModelId={modelSettings.selectedModelId}
        apiKey={modelSettings.apiKey}
        notice={modelSettings.settingsNotice}
        onChangeModel={(modelId) => void modelSettings.selectModel(modelId)}
        onChangeApiKey={modelSettings.setApiKey}
        onClose={() => modelSettings.setSettingsOpen(false)}
        onSaveKey={() => void modelSettings.saveVolcengineKey()}
      />

      <HistoryDrawer
        variant="drawer"
        open={historyOpen}
        conversations={conversations}
        conversationId={chat.conversationId}
        connected={connected}
        isSending={chat.isSending}
        onClose={() => setHistoryOpen(false)}
        onNewConversation={startNewConversation}
        onSelect={selectConversation}
      />

      <section
        className={`workspace-page ${
          chat.messages.length ? "chat-mode" : "home-mode"
        }`}
      >
        {chat.messages.length === 0 ? (
          <HomeView
            connected={connected}
            notice={chat.notice}
            input={chat.input}
            selectedModelName={selectedModelName}
            isSending={chat.isSending}
            canSend={canSend}
            onChangeInput={chat.setInput}
            onOpenHistory={() => setHistoryOpen(true)}
            onOpenSettings={() => modelSettings.setSettingsOpen(true)}
            onSend={() => void chat.sendMessage(chat.input)}
            onStop={() => void chat.stopReply()}
            onPrompt={chat.setInput}
          />
        ) : (
          <div className="agent-workbench">
            <HistoryDrawer
              variant="rail"
              open
              conversations={conversations}
              conversationId={chat.conversationId}
              connected={connected}
              isSending={chat.isSending}
              onClose={() => undefined}
              onNewConversation={startNewConversation}
              onSelect={selectConversation}
            />
            <ChatView
              messages={chat.messages}
              cursor={chat.cursor}
              notice={chat.notice}
              input={chat.input}
              selectedModelName={selectedModelName}
              conversationTitle={conversationTitle}
              isSending={chat.isSending}
              canSend={canSend}
              onChangeInput={chat.setInput}
              onLoadOlder={() =>
                chat.conversationId
                  ? void chat.selectConversation(chat.conversationId, true)
                  : undefined
              }
              onNewConversation={startNewConversation}
              onOpenHistory={() => setHistoryOpen(true)}
              onOpenSettings={() => modelSettings.setSettingsOpen(true)}
              onSend={() => void chat.sendMessage(chat.input)}
              onStop={() => void chat.stopReply()}
              onToggleReasoning={chat.toggleReasoning}
            />
            <AgentContextRail
              conversationId={chat.conversationId}
              conversationStatus={activeConversation?.status}
              workspace={activeConversation?.workspace}
              selectedModelName={selectedModelName}
              connected={connected}
              isSending={chat.isSending}
            />
          </div>
        )}
      </section>
    </main>
  );
}
