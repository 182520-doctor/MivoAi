# 造境后端分层架构

日期：2026-09-06

## 设计目标

后端采用轻量分层架构，在不过度设计 MVP 的前提下，把 HTTP、业务规则、持久化和外部协议隔离。公开接口和 SQLite 数据结构保持兼容，未来增加图片生成、任务队列或 PostgreSQL 时，可以替换单层实现而不重写整个系统。

## 目录职责

```text
apps/api/app
├── api
│   ├── errors.py                 HTTP 异常和状态码转换
│   └── routes
│       ├── conversations.py      会话 REST/SSE 接口
│       └── status.py             健康检查和旧接口兼容
├── core
│   ├── config.py                 环境变量与路径配置
│   ├── exceptions.py             领域和集成异常
│   ├── interfaces.py             CodexClient 接口契约
│   ├── protocol_logging.py       JSON-RPC 日志与脱敏
│   └── security.py               浏览器 Origin 策略
├── db
│   ├── database.py               SQLite 连接、锁和事务
│   └── repositories.py           会话、回合、消息和提交记录 SQL
├── models
│   ├── codex.py                  Codex 事件类型
│   └── conversation.py           API 请求与领域状态
├── services
│   ├── codex_app_server.py       子进程和 JSON-RPC 通信
│   └── conversation_service.py   会话业务编排
├── utils
│   └── sse.py                    SSE 序列化
└── main.py                       依赖装配与生命周期
```

## 依赖规则

依赖只能从外层流向内层：

```text
API -> Service -> Repository -> Database
              -> CodexClient interface <- Codex App Server implementation
```

- `api` 可以依赖 `services` 和 `models`，负责 HTTP，不写 SQL。
- `services` 可以依赖 `db`、`models` 和 `core`，不导入 FastAPI。
- `db` 只处理持久化，不调用 Codex，也不决定 HTTP 状态码。
- `models` 不依赖框架外层，作为各层之间的数据契约。
- `core` 放置全局配置、抽象接口和基础设施，不放具体业务流程。
- `utils` 必须保持纯函数，不能持有数据库或网络连接。
- `main.py` 是唯一的依赖装配入口。

## 消息请求流程

1. `api/routes/conversations.py` 验证 `MessageCreate`，调用 `ConversationService.start_message`。
2. Service 查询 Repository，检查会话是否存在、是否正在回复、消息 ID 是否重复。
3. Repository 在 SQLite 中写入幂等提交记录、本地 turn、用户消息和助手占位消息。
4. Service 创建 `ActiveTurn` 和异步任务，并立即把事件迭代器返回 API。
5. `CodexAppServerClient` 通过 stdio 发送 `thread/start`、`thread/resume` 或 `turn/start`。
6. App Server 的 JSON-RPC 通知按 `threadId` 分发到独立队列。
7. Codex Service 将原始通知归一化为 `meta/reasoning_started/reasoning_delta/reasoning_completed/reasoning_usage/delta/message_completed/done/error`。
8. Conversation Service 一边把事件放入 SSE 队列返回浏览器，一边把回答 delta、思考文本和 reasoning token 写入 SQLite。
9. 无论成功、失败或取消，Service 都在 `finally` 中清理活动状态并完成提交记录。

## 中止流程

中止接口首先向 App Server 发送 `turn/interrupt`，然后立即向浏览器发送 `interrupted` 终止事件并取消本地等待任务。若 App Server 表示该轮刚好已经结束，则按幂等成功处理，避免竞态产生 `500`。

## 数据与并发

- SQLite 新增 `sessions`、`turns`、`messages` 和增强后的 `submissions` 表，`conversations` 作为旧版本兼容表保留。
- 浏览器会话历史只读取 `messages` 和 `turns`，不会再调用 `thread/turns/list` 去查看本地 Codex 会话历史。
- `Database.transaction` 使用进程内重入锁，保证 FastAPI 并发请求下的写事务完整。
- 活动生成任务仅保存在 `ConversationService` 内存中，服务重启后页面仍显示 SQLite 中已经落库的历史。
- `clientMessageId` 在数据库中唯一，用于阻止浏览器重试造成重复提交。

## 扩展约定

增加图片生成时，建议新增 `GenerationService`、`GenerationRepository` 和 `api/routes/generations.py`。模型厂商适配器实现统一的 `ImageProvider` 接口，具体 OpenAI、火山或其他 Provider 不应进入路由层。耗时任务进一步接入队列时，API 和领域模型可以保持不变。

## 验证命令

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/api
uv run pytest -q
uv run ruff check .
```
