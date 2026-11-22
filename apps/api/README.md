# MivoAi API

MivoAi API 是一个分层 FastAPI 网关，负责对接本地 Codex App Server、会话管理、模型/供应商配置，以及图片和视频生成任务。

## 环境要求

- Python 3.12+
- uv
- Codex CLI（已安装并配置模型供应商）；通过 npm 安装时还需要 Node.js

确认 uv 是否可用：

```powershell
uv --version
```

如果本机未安装 uv，可在 PowerShell 中安装：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 安装依赖

在 `apps/api` 目录运行：

```powershell
uv sync
```

该命令会根据 `pyproject.toml` 和 `uv.lock` 创建 `.venv` 并安装运行、开发依赖。

## 启动服务

```powershell
uv run fastapi dev app/main.py
```

或直接通过模块入口启动：

```powershell
uv run python -m app.main
```

默认监听地址为：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 常用命令

运行测试：

```powershell
uv run pytest
```

代码检查：

```powershell
uv run ruff check .
```

自动修复可修复的 lint 问题：

```powershell
uv run ruff check . --fix
```

## 配置项

应用启动时会从环境变量读取配置；未设置时使用本地默认值。

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `CODEX_BINARY` | Codex App Server 可执行文件路径；不设置时会先找 `<repo>/vendor/codex/bin`，再回退到 PATH 中的 `codex` | 自动解析 |
| `CODEX_WORKSPACE` | Codex 工作目录 | `<repo>/runtime/chat` |
| `DATABASE_PATH` | SQLite 会话数据库路径 | `<repo>/apps/api/data/conversations.db` |
| `CODEX_PROTOCOL_LOG_PATH` | Codex 协议日志路径 | `<repo>/runtime/logs/codex-protocol.log` |
| `CODEX_PROTOCOL_LOG` | 是否启用协议日志，设为 `0` 可关闭 | `1` |
| `ZAOJING_SECRET_KEY_PATH` | 本地密钥文件路径 | `<repo>/runtime/secrets/master.key` |
| `ZAOJING_ASSET_DIR` | 生成素材存储目录 | `<repo>/apps/api/data/assets` |

PowerShell 示例：

```powershell
$env:DATABASE_PATH = "C:\tmp\mivoai-conversations.db"
uv run fastapi dev app/main.py
```

## Windows 排查

如果提示 `Codex binary not found`，先用 `Get-Command codex` 确认 CLI 已安装且在 PATH 中。
也可以显式指定路径：

```powershell
$env:CODEX_BINARY = "$env:APPDATA\npm\codex.cmd"
uv run python -m app.main
```

API 在 Windows 启动 Codex 子进程时使用 `CREATE_NO_WINDOW`，避免弹出控制台黑窗。
更新代码后需重启 API；PyCharm 中直接运行 `app/main.py` 的进程不会自动加载代码修改。

`GET /api/status` 的认证字段含义：

- `authenticated`：满足当前供应商的 OpenAI 认证要求，供前端判断连接状态。
- `accountAuthenticated`：Codex 是否返回 OpenAI 账户信息。
- `requiresOpenaiAuth`：当前供应商是否要求 OpenAI 登录；初始化前为 `null`。

自定义供应商返回 `account: null, requiresOpenaiAuth: false` 时，`authenticated` 为 `true`。
这不代表已经验证供应商的 API Key、网络或模型可用性；实际请求失败仍需查看回合错误。
协议日志以 UTF-8 写入，可用 `Get-Content -Encoding utf8 <日志路径>` 读取。
HTTP 200 和 `turn/started` 仅表示请求已接收；模型回复应出现 `item/agentMessage/delta`
或 `item/completed`（`agentMessage`），并最终出现 `turn/completed`。

## 主要接口

- `GET /health`：健康检查
- `GET /api/status`：运行状态
- `GET /api/conversations`：会话列表
- `POST /api/conversations`：创建会话
- `GET /api/conversations/{conversation_id}/messages`：读取会话消息
- `WS /api/conversations/{conversation_id}/ws`：发送消息、接收流式事件和中断
- `POST /api/conversations/{conversation_id}/messages`：已移除，返回 410
- `POST /api/conversations/{conversation_id}/interrupt`：中断会话
- `GET /api/models`：模型列表
- `GET /api/preferences`：读取偏好配置
- `PUT /api/preferences`：更新偏好配置
- `PUT /api/providers/{provider_id}/credential`：保存供应商凭据
- `POST /api/generations`：创建生成任务
- `GET /api/generations/{task_id}`：查询生成任务
- `GET /api/assets/{asset_id}`：读取生成素材

## WebSocket 流式聊天

链路：浏览器 WebSocket -> FastAPI -> Codex App Server（stdio JSONL）。
协议参考仓库的 `docs/codex-app-server.md`。后端持续读取 Codex 事件，不等待整段回答完成。
浏览器进入会话时创建一个连接，同一会话的连续回合和中断复用该连接。
回合结束不关闭连接；切换会话或离开页面时关闭。历史记录继续通过 HTTP 读取。

本地默认直连 `ws://127.0.0.1:8000/api/conversations/{id}/ws`（主机名随网页地址）。
前端可在启动或构建前设置 `NEXT_PUBLIC_API_WS_URL`，例如 `ws://127.0.0.1:8000`。
HTTPS 网页默认连接同域 `wss://`，需要反向代理将 `/api/conversations/*/ws` 的
WebSocket Upgrade 请求转发到 FastAPI，并在代理处终止 TLS。Next.js 的 HTTP rewrite
不作为本地 WebSocket 链路。生产域名必须加入后端 `Settings.allowed_origins` 和
`allowed_hosts`；现有应用仍面向本地使用，公开部署前需要应用级身份认证。

连接建立后，服务端返回 `ready`；每次发送消息使用以下 JSON 文本帧：

```json
{"type":"message","payload":{"message":"你好","clientMessageId":"唯一请求ID","providerId":"codex_local","modelId":"codex-local-default"}}
```

停止当前回复，在同一连接发送：

```json
{"type":"interrupt"}
```

服务端每帧一条 JSON：

- `meta`：线程、回合和本地助手消息 ID。
- `ready`：会话连接就绪；`ping` / `pong` 用于空闲心跳。
- `output`：`content` 为最终回答，`reasoning` 为思考区内容；两个字段均为当前快照，前端替换显示。
- `reasoning_usage`：服务端提供的推理 token 计数。
- `delta`、`reasoning_delta` 等：其他供应商适配器的文本增量。
- `done`：回合完成或中断。
- `error`：请求或生成失败；请求校验错误附带 `code`（400/404/409/422/502）。

回合事件携带 `clientMessageId`，用于关联消息。`done` 只结束当前回合，
校验失败也保留连接，可继续发送新消息；前端每 20 秒发送心跳。

`agentMessage.phase=commentary` 与服务端公开的推理摘要显示在思考区，
`phase=final_answer` 显示在正文。按 `itemId` 合并增量与完成事件，避免重复内容。
若服务器未提供阶段字段，生成中的文本暂放思考区，消息完成后移入正文。
不会推测或补造服务端未公开的思考文本。

连接断开会中断该连接发起的回合，并保留已生成内容；重新打开会话读取历史。
不会自动重发用户消息，以免重复生成。重复 `clientMessageId` 返回 409。

## 项目结构

```text
app/
  api/          HTTP 路由和错误处理
  core/         配置、安全、接口和异常定义
  db/           SQLite 数据库与仓储
  models/       请求和响应模型
  services/     业务服务与外部集成
  utils/        SSE、历史记录等工具
tests/          测试用例
```
