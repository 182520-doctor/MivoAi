import type { ConnectionStatus, MessagePayload, ServerEvent } from "../types";

type PendingTurn = {
  id: string;
  onEvent: (event: ServerEvent) => void;
  resolve: () => void;
  reject: (error: Error) => void;
};

export function sessionSocketUrl(
  id: string,
  location: Pick<Location, "protocol" | "host" | "hostname">,
) {
  const base =
    process.env.NEXT_PUBLIC_API_WS_URL ||
    (location.protocol === "https:"
      ? `wss://${location.host}`
      : `ws://${location.hostname}:8000`);
  const url = new URL(base);
  if (!["ws:", "wss:"].includes(url.protocol))
    throw new Error("WebSocket 地址必须使用 ws 或 wss");
  url.pathname = `/api/conversations/${encodeURIComponent(id)}/ws`;
  url.search = "";
  url.hash = "";
  return url.toString();
}

// One instance belongs to one selected conversation, independent of React renders.
export class SessionSocket {
  private socket: WebSocket | null = null;
  private ready: Promise<void> | null = null;
  private rejectReady: ((error: Error) => void) | null = null;
  private pending: PendingTurn | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private lastPong = 0;

  constructor(
    private readonly url: string,
    private readonly onStatus: (status: ConnectionStatus) => void,
    private readonly onError: (error: Error) => void,
    private readonly createSocket = (url: string) => new WebSocket(url),
  ) {}

  connect(): Promise<void> {
    if (this.ready && this.socket && this.socket.readyState < 2)
      return this.ready;
    this.onStatus("connecting");
    let socket: WebSocket;
    try {
      socket = this.createSocket(this.url);
    } catch (error) {
      this.onStatus("disconnected");
      return Promise.reject(error);
    }
    this.socket = socket;
    this.ready = new Promise<void>((resolve, reject) => {
      this.rejectReady = reject;
      this.timer = setTimeout(
        () => this.fail(new Error("连接后端超时")),
        15000,
      );
      socket.onmessage = (frame) => {
        if (this.socket !== socket) return;
        try {
          const event = JSON.parse(frame.data) as ServerEvent;
          if (!event || typeof event.type !== "string")
            throw new Error("后端返回无效消息");
          if (event.type === "ready") {
            this.clearTimers();
            this.rejectReady = null;
            this.lastPong = Date.now();
            this.heartbeat = setInterval(() => {
              if (Date.now() - this.lastPong > 60000) {
                this.fail(new Error("会话连接超时，请重新连接"));
              } else if (socket.readyState === 1) {
                socket.send(JSON.stringify({ type: "ping" }));
              }
            }, 20000);
            this.onStatus("connected");
            resolve();
          } else if (event.type === "pong") {
            this.lastPong = Date.now();
          } else {
            const turn = this.pending;
            if (
              turn &&
              (!event.clientMessageId || event.clientMessageId === turn.id)
            ) {
              turn.onEvent(event);
              if (event.type === "done" || event.type === "error") {
                this.pending = null;
                if (event.type === "done") turn.resolve();
                else turn.reject(new Error(event.message));
              }
            } else if (event.type === "error" && !turn) {
              this.fail(new Error(event.message));
            }
          }
        } catch (error) {
          this.fail(
            error instanceof Error ? error : new Error("后端返回无效消息"),
          );
        }
      };
      socket.onerror = () => {
        if (this.socket === socket)
          this.fail(new Error("无法连接后端，请检查服务和连接地址"));
      };
      socket.onclose = () => {
        if (this.socket === socket)
          this.fail(new Error("会话连接已断开，已生成内容保存在历史中"));
      };
    });
    return this.ready;
  }

  send(
    payload: MessagePayload,
    onEvent: PendingTurn["onEvent"],
  ): Promise<void> {
    if (this.pending) return Promise.reject(new Error("当前会话正在回复"));
    if (this.socket?.readyState !== 1)
      return Promise.reject(new Error("会话尚未连接"));
    return new Promise((resolve, reject) => {
      this.pending = { id: payload.clientMessageId, onEvent, resolve, reject };
      try {
        this.socket!.send(JSON.stringify({ type: "message", payload }));
      } catch (error) {
        this.pending = null;
        reject(error);
      }
    });
  }

  interrupt() {
    if (this.pending && this.socket?.readyState === 1) {
      this.socket.send(JSON.stringify({ type: "interrupt" }));
    }
  }

  close() {
    this.dispose(new Error("会话连接已关闭"));
  }

  private fail(error: Error) {
    this.dispose(error);
    this.onError(error);
  }

  private dispose(error: Error) {
    const socket = this.socket;
    this.socket = null;
    this.ready = null;
    this.clearTimers();
    this.rejectReady?.(error);
    this.rejectReady = null;
    this.pending?.reject(error);
    this.pending = null;
    socket?.close();
    this.onStatus("disconnected");
  }

  private clearTimers() {
    if (this.timer) clearTimeout(this.timer);
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.timer = null;
    this.heartbeat = null;
  }
}
