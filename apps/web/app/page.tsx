"use client";

import {
  ArrowUp,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleStop,
  FolderOpen,
  History,
  Home as HomeIcon,
  Image as ImageIcon,
  LayoutGrid,
  Lightbulb,
  Menu,
  MessageSquareText,
  Plus,
  Ratio,
  Search,
  Sparkles,
  Settings2,
  Video,
  WandSparkles,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "streaming" | "done" | "error";
  reasoning?: string;
  reasoningTokens?: number;
  reasoningOpen?: boolean;
};

type ServerEvent = {
  type:
    | "meta"
    | "reasoning_started"
    | "reasoning_delta"
    | "reasoning_completed"
    | "reasoning_usage"
    | "delta"
    | "message_completed"
    | "done"
    | "error";
  text?: string;
  message?: string;
  status?: string;
  tokens?: number;
  assistantMessageId?: string;
};

type Health = {
  status: "ok" | "degraded";
  app_server: {
    running: boolean;
    authenticated: boolean;
    version: string | null;
    platform: string | null;
  };
};

type Model = {
  id: string;
  providerId: string;
  providerName: string;
  name: string;
  modelKey: string;
  capabilities: string[];
  executionMode: string;
  configured: boolean;
  integrationStatus: string;
};

const quickActions = [
  { icon: Lightbulb, title: "创意策划", detail: "把模糊灵感变成清晰方案", prompt: "帮我把一个模糊的创意整理成清晰方案" },
  { icon: ImageIcon, title: "画面提示词", detail: "设计构图、风格与光影", prompt: "为一张产品海报设计画面和提示词" },
  { icon: Video, title: "短片故事", detail: "从故事梗概到分镜节奏", prompt: "和我一起头脑风暴一个短片故事" },
  { icon: WandSparkles, title: "灵感扩写", detail: "延展更多可执行的方向", prompt: "请基于我的想法延展三个不同的创意方向" },
];

const galleryItems = [
  { className: "art-one", label: "雪山叙事", prompt: "帮我构思一个发生在雪山中的电影感故事" },
  { className: "art-two", label: "玻璃花语", prompt: "设计一组透明玻璃花的视觉概念" },
  { className: "art-three", label: "太空伙伴", prompt: "构思一个猫咪宇航员的短片创意" },
  { className: "art-four", label: "未来绿洲", prompt: "设计一个未来生态城市的世界观" },
];

export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("codex-local-default");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [settingsNotice, setSettingsNotice] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  function patchAssistant(
    assistantId: string,
    updater: (message: Message) => Message,
  ) {
    setMessages((current) => current.map((item) => (
      item.id === assistantId ? updater(item) : item
    )));
  }

  async function refreshList() {
    const response = await fetch("/api/conversations");
    if (response.ok) setConversations(await response.json());
  }

  async function loadModelSettings() {
    const [modelResponse, preferenceResponse] = await Promise.all([
      fetch("/api/models"),
      fetch("/api/preferences"),
    ]);
    if (modelResponse.ok) setModels(await modelResponse.json());
    if (preferenceResponse.ok) {
      const preferences = await preferenceResponse.json();
      if (preferences.defaultTextModelId) setSelectedModelId(preferences.defaultTextModelId);
    }
  }

  async function saveVolcengineKey() {
    setSettingsNotice("");
    const response = await fetch("/api/providers/volcengine/credential", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey }),
    });
    if (!response.ok) {
      setSettingsNotice("保存火山引擎 API Key 失败");
      return;
    }
    setApiKey("");
    setSettingsNotice("已保存，Key 不会返回到浏览器");
    await loadModelSettings();
  }

  async function saveModelPreference(modelId: string) {
    setSelectedModelId(modelId);
    await fetch("/api/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ defaultTextModelId: modelId }),
    });
  }

  async function selectConversation(id: string, older = false) {
    try {
      const query = older && cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
      const response = await fetch(`/api/conversations/${id}/messages${query}`);
      if (!response.ok) throw new Error("无法加载会话历史");
      const data = await response.json();
      setConversationId(id);
      setSidebarOpen(false);
      localStorage.setItem("zaojing-conversation", id);
      setMessages((current) => (older ? [...data.messages, ...current] : data.messages));
      setCursor(data.cursor);
      setNotice(data.active ? "此会话仍在回复，请稍后刷新会话。" : "");
    } catch (error) {
      setNotice((error as Error).message);
    }
  }

  useEffect(() => {
    refreshList();
    loadModelSettings();
    const saved = localStorage.getItem("zaojing-conversation");
    if (saved) selectConversation(saved);
    const check = () => fetch("/api/status")
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth(null));
    check();
    const timer = setInterval(check, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function newConversation() {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    localStorage.removeItem("zaojing-conversation");
    setCursor(null);
    setNotice("");
    setInput("");
    setIsSending(false);
    setSidebarOpen(false);
  }

  async function sendMessage(text: string) {
    const message = text.trim();
    if (!message || isSending) return;

    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: message };
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: "assistant", content: "", status: "streaming" },
    ]);
    setInput("");
    setIsSending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    let currentAssistantId = assistantId;

    try {
      let cid = conversationId;
      if (!cid) {
        const created = await fetch("/api/conversations", { method: "POST" });
        if (!created.ok) throw new Error("创建会话失败");
        cid = (await created.json()).id;
        setConversationId(cid);
        localStorage.setItem("zaojing-conversation", cid!);
      }
      const response = await fetch(`/api/conversations/${cid}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          clientMessageId: userMessage.id,
          providerId: models.find((item) => item.id === selectedModelId)?.providerId ?? "codex_local",
          modelId: selectedModelId,
        }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error("后端没有返回有效数据");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;
          const event: ServerEvent = JSON.parse(dataLine.slice(6));
          if (event.type === "meta" && event.assistantMessageId) {
            patchAssistant(currentAssistantId, (item) => ({ ...item, id: event.assistantMessageId! }));
            currentAssistantId = event.assistantMessageId;
          }
          if (event.type === "reasoning_started") {
            patchAssistant(currentAssistantId, (item) => ({
              ...item,
              reasoning: event.text || item.reasoning || "正在分析你的需求…",
              reasoningOpen: false,
            }));
          }
          if (event.type === "reasoning_delta" && event.text) {
            patchAssistant(currentAssistantId, (item) => ({
              ...item,
              reasoning: `${item.reasoning ?? ""}${event.text}`,
              reasoningOpen: false,
            }));
          }
          if (event.type === "reasoning_completed") {
            patchAssistant(currentAssistantId, (item) => ({
              ...item,
              reasoning: event.text || item.reasoning || "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。",
              reasoningOpen: false,
            }));
          }
          if (event.type === "reasoning_usage") {
            patchAssistant(currentAssistantId, (item) => ({
              ...item,
              reasoningTokens: event.tokens ?? item.reasoningTokens,
              reasoning: item.reasoning || (
                event.tokens && event.tokens > 0
                  ? "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。"
                  : item.reasoning
              ),
            }));
          }
          if (event.type === "message_completed") {
            patchAssistant(currentAssistantId, (item) => (
              { ...item, content: event.text ?? item.content }
            ));
          }
          if (event.type === "delta" && event.text) {
            patchAssistant(currentAssistantId, (item) => (
              { ...item, content: item.content + event.text }
            ));
          }
          if (event.type === "done") {
            completed = true;
            if (event.status === "interrupted") setNotice("回复已停止");
            patchAssistant(currentAssistantId, (item) => ({ ...item, status: "done" }));
          }
          if (event.type === "error") throw new Error(event.message ?? "Codex 回复失败");
        }
        if (done) break;
      }
      if (!completed) throw new Error("连接提前结束，请重新打开会话查看结果");
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setNotice((error as Error).message);
        setMessages((current) => current.map((item) => (
          item.id === currentAssistantId
            ? { ...item, status: "error", content: item.content || (error as Error).message }
            : item
        )));
      }
    } finally {
      setIsSending(false);
      abortRef.current = null;
      refreshList();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      sendMessage(input);
    }
  }

  async function stopReply() {
    if (!conversationId) return;
    const response = await fetch(`/api/conversations/${conversationId}/interrupt`, { method: "POST" });
    if (!response.ok) setNotice("停止请求失败，请重试");
  }

  function toggleReasoning(messageId: string) {
    setMessages((current) => current.map((message) => (
      message.id === messageId
        ? { ...message, reasoningOpen: !message.reasoningOpen }
        : message
    )));
  }

  function renderReasoning(message: Message) {
    if (message.role !== "assistant" || (!message.reasoning && !message.reasoningTokens)) {
      return null;
    }
    const tokenText = message.reasoningTokens ? ` · ${message.reasoningTokens} reasoning tokens` : "";
    return (
      <div className={`reasoning-panel ${message.reasoningOpen ? "open" : ""}`}>
        <button type="button" onClick={() => toggleReasoning(message.id)}>
          <ChevronDown size={14} />
          <span>{message.status === "streaming" ? "正在思考" : "思考过程"}{tokenText}</span>
        </button>
        {message.reasoningOpen && (
          <div className="reasoning-body">
            <Markdown remarkPlugins={[remarkGfm]}>{message.reasoning || "已进行内部思考，当前 Codex App Server 未暴露详细思考文本。"}</Markdown>
          </div>
        )}
      </div>
    );
  }

  function renderComposer(compact = false) {
    const selectedModel = models.find((item) => item.id === selectedModelId);
    const canSend = selectedModel?.providerId === "volcengine"
      ? Boolean(selectedModel.configured && selectedModel.integrationStatus === "ready")
      : connected;
    return (
      <form className={`composer ${compact ? "compact" : "studio"}`} onSubmit={submit}>
        <textarea
          aria-label="发送消息"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的创意，和 Agent 一起把它变清晰…"
          rows={compact ? 2 : 4}
        />
        <div className="composer-footer">
          <div className="composer-tools">
            <button type="button" className="tool-pill primary" onClick={() => setSettingsOpen(true)}><Bot size={17} />{selectedModel?.name ?? "本地 Codex Agent"}<ChevronDown size={14} /></button>
            <button type="button" className="tool-pill icon-only" title="模型与偏好设置" onClick={() => setSettingsOpen(true)}><Settings2 size={17} /></button>
            {!compact && <button type="button" className="tool-pill" onClick={() => setInput("请帮我完善这个创意的执行方案：")}><WandSparkles size={16} />创意策划</button>}
            {!compact && <button type="button" className="tool-pill icon-only" title="画面比例"><Ratio size={17} /></button>}
          </div>
          <div className="submit-area">
            {!compact && <span><Sparkles size={14} /> 本地 Codex</span>}
            {isSending ? (
              <button className="send-button stop" type="button" onClick={stopReply} title="停止回复"><CircleStop size={20} /></button>
            ) : (
              <button className="send-button" type="submit" disabled={!input.trim() || !canSend} title="发送消息"><ArrowUp size={20} /></button>
            )}
          </div>
        </div>
      </form>
    );
  }

  const connected = health?.status === "ok" && health.app_server.authenticated;
  const selectedModel = models.find((item) => item.id === selectedModelId);

  return (
    <main className="app-shell">
      <aside className="rail" aria-label="主导航">
        <button className="logo-button" type="button" title="造境" onClick={newConversation}><Sparkles size={25} /></button>
        <nav>
          <button className="rail-item active" type="button" onClick={newConversation}><HomeIcon size={21} /><span>灵感</span></button>
          <button className="rail-item" type="button" onClick={() => setInput("帮我构思一个新的创意项目")}><WandSparkles size={21} /><span>创作</span></button>
          <button className="rail-item" type="button" onClick={() => setSidebarOpen(true)}><History size={21} /><span>对话</span></button>
          <button className="rail-item" type="button"><FolderOpen size={21} /><span>资产</span></button>
          <button className="rail-item" type="button"><LayoutGrid size={21} /><span>画布</span></button>
        </nav>
        <div className="rail-spacer" />
        <span className={`rail-status ${connected ? "online" : ""}`} title={connected ? "Codex 已连接" : "Codex 未连接"} />
      </aside>

      {sidebarOpen && <button className="drawer-backdrop" type="button" aria-label="关闭会话列表" onClick={() => setSidebarOpen(false)} />}
      {settingsOpen && <button className="drawer-backdrop" type="button" aria-label="关闭模型设置" onClick={() => setSettingsOpen(false)} />}
      <aside className={`settings-drawer ${settingsOpen ? "open" : ""}`}>
        <div className="drawer-head"><div><Settings2 size={18} /><strong>模型与偏好</strong></div><button type="button" title="关闭" onClick={() => setSettingsOpen(false)}>×</button></div>
        <p className="settings-help">选择默认文本模型。火山方舟模型需要填入你自己的 API Key，密钥只保存在本地后端。</p>
        <label className="settings-field">默认文本模型
          <select value={selectedModelId} onChange={(event) => saveModelPreference(event.target.value)}>
            {models.filter((model) => model.capabilities.includes("text")).map((model) => (
              <option key={model.id} value={model.id}>{model.providerName} / {model.name}{model.integrationStatus !== "ready" ? "（待接入）" : ""}</option>
            ))}
          </select>
        </label>
        {selectedModel?.providerId === "volcengine" && <>
          <label className="settings-field">火山引擎 API Key
            <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="输入 Ark API Key" autoComplete="off" />
          </label>
          <button className="save-settings" type="button" disabled={!apiKey.trim()} onClick={saveVolcengineKey}>保存 Key</button>
        </>}
        {settingsNotice && <p className="settings-notice">{settingsNotice}</p>}
        <div className="settings-status"><span className={selectedModel?.configured || selectedModel?.providerId === "codex_local" ? "online" : ""} /><span>{selectedModel?.configured || selectedModel?.providerId === "codex_local" ? "当前模型已配置" : "当前模型尚未配置 API Key"}</span></div>
      </aside>
      <aside className={`history-drawer ${sidebarOpen ? "open" : ""}`}>
        <div className="drawer-head"><div><Sparkles size={18} /><strong>造境</strong></div><button type="button" title="关闭" onClick={() => setSidebarOpen(false)}>×</button></div>
        <button className="new-chat" type="button" disabled={isSending} onClick={newConversation}><Plus size={17} />新建对话</button>
        <span className="drawer-label">最近对话</span>
        <div className="conversation-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              disabled={isSending}
              className={`conversation ${conversation.id === conversationId ? "active" : ""}`}
              type="button"
              onClick={() => selectConversation(conversation.id)}
            >
              <MessageSquareText size={16} /><span>{conversation.title}</span>
            </button>
          ))}
        </div>
        <div className="connection"><span className={connected ? "online" : ""} /><div><strong>{connected ? "Codex 已连接" : "Codex 未连接"}</strong><small>本地 App Server</small></div></div>
      </aside>

      <section className={`workspace ${messages.length ? "chat-mode" : "home-mode"}`}>
        {messages.length === 0 ? (
          <div className="home-scroll">
            <header className="home-header">
              <button className="mobile-menu" type="button" title="打开导航" onClick={() => setSidebarOpen(true)}><Menu size={21} /></button>
              <span className={`server-state ${connected ? "online" : ""}`}><i />{connected ? "Codex 已连接" : "等待连接"}</span>
            </header>
            <section className="creation-zone">
              <h1>开启你的 <em>Agent 创作</em>，即刻造梦！</h1>
              {renderComposer()}
              {notice && <p className="notice" role="alert">{notice}</p>}
              <div className="quick-actions">
                {quickActions.map(({ icon: Icon, title, detail, prompt }, index) => (
                  <button key={title} type="button" onClick={() => setInput(prompt)}>
                    <span className={`quick-icon tone-${index + 1}`}><Icon size={20} /></span>
                    <span><strong>{title}</strong><small>{detail}</small></span>
                    <ArrowUp size={16} />
                  </button>
                ))}
              </div>
            </section>
            <section className="discover">
              <div className="discover-head">
                <div className="discover-tabs"><button className="active" type="button">发现</button><button type="button">技能</button><button type="button">短片</button><button type="button">灵感</button></div>
                <label><Search size={17} /><input aria-label="搜索灵感" placeholder="搜索创意灵感" /></label>
              </div>
              <div className="gallery">
                {galleryItems.map((item) => (
                  <button className="gallery-item" type="button" key={item.label} onClick={() => setInput(item.prompt)}>
                    <span className={`gallery-art ${item.className}`} />
                    <span className="gallery-label"><strong>{item.label}</strong><small>用 Agent 继续创作</small></span>
                  </button>
                ))}
              </div>
            </section>
          </div>
        ) : (
          <>
            <header className="chat-header">
              <div><button className="mobile-menu" type="button" title="打开导航" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button><span className="chat-mark"><Bot size={17} /></span><div><h1>创意 Agent</h1><small>与 Codex 一起完善你的想法</small></div></div>
              <button className="header-new" type="button" onClick={newConversation}><Plus size={16} />新对话</button>
            </header>
            <div className="conversation-area">
              <div className="message-list">
                {cursor && <button className="load-more" onClick={() => conversationId && selectConversation(conversationId, true)}>加载更早消息</button>}
                {messages.map((message) => (
                  <article className={`message ${message.role}`} key={message.id}>
                    {message.role === "assistant" && <div className="avatar"><Sparkles size={15} /></div>}
                    <div className="message-content">
                      {message.role === "assistant" && <span className="message-author">造境 Agent</span>}
                      {renderReasoning(message)}
                      <div className="markdown"><Markdown remarkPlugins={[remarkGfm]}>{message.content || "正在生成回复…"}</Markdown></div>
                      {message.role === "assistant" && message.status === "streaming" && <span className="typing-dot" />}
                      {message.status === "done" && <span className="message-status"><CheckCircle2 size={13} />由本地 Codex 生成</span>}
                      {message.status === "error" && <span className="message-error">连接出现问题</span>}
                    </div>
                  </article>
                ))}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className="composer-dock">
              {notice && <p className="notice" role="alert">{notice}</p>}
              {renderComposer(true)}
              <p>Agent 可能会犯错，请核对重要信息</p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
