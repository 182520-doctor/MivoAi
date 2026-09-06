# 造境 Agent MVP

一个受即梦工作流启发的本地 Agent 网站最小版本。浏览器通过 Next.js 同源接口访问 FastAPI，FastAPI 再以 JSON-RPC 连接本机的 Codex App Server。模型不在本机运行；App Server 使用本机现有的 Codex 登录状态调用模型。

## 已实现

- 新建和切换对话
- 流式显示 Agent 回复
- 折叠展示 Codex 思考/推理过程和 reasoning token
- Markdown/GFM 渲染，支持表格、列表、代码块
- 多轮上下文与服务重启后的会话恢复
- 中止正在生成的回复
- SQLite 保存业务会话、回合、消息详情与提交记录；页面历史以 SQLite 为准
- Codex App Server 运行、登录状态检查
- 桌面端和移动端自适应界面
- 前端只访问同源 `/api`，不暴露 App Server
- 火山方舟文本/多模态 Chat API 接入，支持用户在页面配置自己的 API Key
- Provider/Model 目录、模型偏好、凭证密文和 `generation_tasks` 请求审计

## 架构

```text
Browser
  -> Next.js (127.0.0.1:3000)
  -> /api rewrite
  -> FastAPI (127.0.0.1:8000)
  -> Codex App Server (stdio / JSON-RPC)
  -> Codex account and remote model
```

关键目录：

- `apps/web`：Next.js 前端
- `apps/api/app/api`：FastAPI 路由和 HTTP 异常转换
- `apps/api/app/services`：会话业务流程和 Codex App Server 集成
- `apps/api/app/db`：SQLite 连接、schema 迁移和 Repository
- `apps/api/app/models`：请求、领域对象和事件类型
- `apps/api/app/core`：配置、接口、异常、安全和协议日志
- `apps/api/app/utils`：SSE 编码和 Codex 历史格式转换
- `vendor/codex`：固定版本的官方 Codex 可执行文件、压缩包和协议 schema
- `scripts`：启动和真实链路验收脚本

完整的分层规范和调用流程见 [`docs/backend-architecture.md`](docs/backend-architecture.md)。

数据库表结构说明见 [`docs/sqlite-schema.md`](docs/sqlite-schema.md)。

火山引擎本次接入记录见 [`docs/volcengine-integration-report.md`](docs/volcengine-integration-report.md)。

多模型网关设计见 [`docs/multi-model-gateway-design.md`](docs/multi-model-gateway-design.md)。

## 一键启动

在仓库根目录运行：

```bash
python scripts/start_local.py
```

看到 `Website: http://127.0.0.1:3000` 后，在浏览器打开 <http://127.0.0.1:3000>。启动窗口需保持打开，按 `Ctrl+C` 会同时停止前后端。

## 手动启动

后端：

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/web
pnpm dev --hostname 127.0.0.1 --port 3000
```

## 验证

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/api
uv run pytest -q
uv run ruff check .

cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/web
pnpm typecheck
pnpm build
```

真实 Codex 链路需先启动后端：

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter
apps/api/.venv/bin/python scripts/check_chat.py
apps/api/.venv/bin/python scripts/check_interrupt.py
```

## 查看 Codex 交互日志

一键启动窗口会实时打印 Codex JSON-RPC 协议日志：

```text
[Codex gateway -> app-server] ...
[Codex app-server -> gateway] ...
```

日志也会持续保存在 `runtime/logs/codex-protocol.log`。

另开终端可实时查看：

```bash
tail -f runtime/logs/codex-protocol.log
```

设置 `CODEX_PROTOCOL_LOG=0` 后启动可关闭协议日志。账号邮箱、token、密码和密钥字段会在输出前自动脱敏。

## 当前边界

这是第一阶段 Agent MVP，只开放文本沟通。图片生成、视频生成、素材上传、作品库和账号系统属于后续阶段。App Server 虽在本机运行，模型推理仍需要网络和有效的 Codex 账号。
