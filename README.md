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
- 独立模型中心：能力筛选、默认模型切换、凭证配置和真实连接测试
- 本地 ComfyUI 接入：Flux 文生图和 Wan 文生视频，任务、进度与素材闭环
- ComfyUI 工作流扫描、导入、API 图转换、真实测试和模型启用管理

## 架构

```text
Browser
  -> Next.js (127.0.0.1:3000)
  -> /api rewrite
  -> FastAPI (127.0.0.1:8010)
  -> Codex App Server (stdio / JSON-RPC)
  -> Codex account and remote model
```

关键目录：

- `apps/web/app/_features`：前端功能域、API 客户端、SSE 解析和状态 Hook
- `apps/web/app/_components`：工作台、会话、消息和设置等展示组件
- `apps/web/app/_shared`：前端通用 HTTP 客户端
- `apps/web/app/page.tsx`：仅作为路由入口，渲染客户端工作台
- `apps/api/app/contexts`：按限界上下文拆分的业务模块
  - `conversations`：会话、Agent 运行时和流式回复
  - `providers`：供应商目录、凭证、文本路由和媒体 Adapter
  - `media_generation`：统一图片/视频生成任务
  - `assets`：素材登记、下载和内容访问
  - `system`：健康检查和兼容接口
- `apps/api/app/shared`：配置、错误、SSE、安全、凭证加密等共享内核
- `apps/api/app/infrastructure/persistence`：SQLite 连接和结构初始化
- `apps/api/app/interfaces`：共享 HTTP 异常转换
- `apps/api/app/composition.py`：依赖装配入口，只有这里绑定具体实现
- `apps/api/app/main.py`：FastAPI 应用工厂和路由注册
- `vendor/codex`：固定版本的官方 Codex 可执行文件、压缩包和协议 schema
- `scripts`：启动和真实链路验收脚本

完整的 DDD 模块边界、依赖规则和调用流程见
[`docs/backend-architecture.md`](docs/backend-architecture.md)。

前端功能域、组件和状态边界见
[`docs/frontend-architecture.md`](docs/frontend-architecture.md)。

数据库表结构说明见 [`docs/sqlite-schema.md`](docs/sqlite-schema.md)。

火山引擎本次接入记录见 [`docs/volcengine-integration-report.md`](docs/volcengine-integration-report.md)。

多模型网关设计见 [`docs/multi-model-gateway-design.md`](docs/multi-model-gateway-design.md)。

ComfyUI 工作流模型管理见
[`docs/comfyui-workflow-management.md`](docs/comfyui-workflow-management.md)。

Codex + ComfyUI 多模态工作台与短剧工作台的 DDD 技术方案见
[`docs/agent-media-studio-ddd-design.md`](docs/agent-media-studio-ddd-design.md)。

## 一键启动

在仓库根目录运行：

```bash
uv run python scripts/start_local.py
```

启动脚本默认使用 3000/8010；端口被占用时会自动选择下一个可用端口，并同步 Next.js
代理地址。看到 `Website: http://127.0.0.1:<port>` 后打开对应地址。启动窗口需保持打开，
按 `Ctrl+C` 会同时停止前后端。Windows 上的构建、API 与 Web 子进程使用隐藏窗口启动，
不会再额外弹出 CMD 控制台。

一键启动默认使用生产构建并通过 `next start` 运行。需要前端热更新时，设置
`ZAOJING_WEB_MODE=dev`，并确保同一项目没有其他 `next dev` 实例。

## 手动启动

后端：

```bash
cd /Users/hwx/Documents/Codex/2026-09-04/an/work/ai-dev-starter/apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
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

当前已接通本地 ComfyUI 的 Flux 文生图和 Wan 文生视频。图片/视频参考素材上传、
图生图、图生视频、音频生成、工作流版本管理和短剧领域模块仍属于后续阶段。
Codex Agent 对话需要有效的本地 Codex 登录；ComfyUI 媒体生成不依赖 Codex 登录。
