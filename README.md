# MivoAi

MivoAi 是一个由 Agent 驱动的本地多模态内容创作平台，支持文本、图片、视频等内容的智能创作与工作流编排。

浏览器直接连接 FastAPI；MivoAi API 是唯一的应用入口，并通过端口适配本地 Codex App Server、ComfyUI、模型供应商、FFmpeg、SQLite 和工作区文件。

## 核心能力

- Agent 对话：流式回复、推理过程、上下文恢复和回合中断
- 创作工作区：小说、剧本、分集、场次、镜头与生产产物
- 多模型供应商：Provider/Model目录、凭证管理和能力路由
- 媒体生成：ComfyUI 工作流发现、导入、参数映射、图片与视频任务
- 素材管理：上传、生成结果登记、本地内容读取和文件绑定
- 媒体处理：FFmpeg、TTS、字幕、转码与确定性处理任务
- Web 工作台：桌面端与移动端适配的流式创作界面

## 系统架构

```text
Browser
  -> FastAPI HTTP / WebSocket (:8010)
  -> 应用模块与端口
  -> Codex / ComfyUI / 模型供应商 / FFmpeg / SQLite / 工作区文件

ComfyUI (:8000)
Next.js (:3000，仅承载浏览器界面，不代理 /api/*)
```

这是一个本地模块化单体，不拆分为微服务。后端采用领域模块优先的 DDD 分层：

```text
apps/api/app/
├── modules/          # 领域、应用用例与端口
├── delivery/         # HTTP 路由、Agent 工具适配器
├── adapters/         # SQLite、Codex、ComfyUI、Provider、媒体、工作区
├── shared/           # 跨模块基础设施与公共类型
├── composition.py    # 依赖装配
└── main.py           # FastAPI 应用入口
```

主要限界上下文：

- `conversations`：对话、Codex线程、回合、消息和流
- `creative_projects`：创作工作区、文档工作流、产物与质量门禁
- `drama`：剧集、场次、镜头、生产运行和审核决策
- `providers`：供应商目录、凭证、模型能力与路由
- `workflows`：ComfyUI工作流发现、导入和参数映射
- `media_generation`：持久化生成任务、重试、取消与结果绑定
- `assets`：素材与本地内容元数据
- `media_processing`：FFmpeg、TTS、字幕和确定性媒体处理

完整约束以 [`AGENTS.md`](AGENTS.md) 为准。

## 仓库结构

```text
apps/
├── api/              # FastAPI、领域模块与基础设施适配器
└── web/              # Next.js App Router 与 React 工作台
 docs/                # 架构、协议、数据库与集成文档
 scripts/             # 本地启动与真实链路检查
 vendor/codex/        # 本地 Codex 运行时与协议资源
```

## 环境要求

- Python 3.12+
- `uv`
- Node.js 和包管理工具
- 可选：本地 ComfyUI（默认地址 `http://127.0.0.1:8000`）
- 可选：已登录或已配置的 Codex App Server
- 可选：FFmpeg

## 一键启动

在仓库根目录运行：

```bash
uv run python scripts/start_local.py
```

启动脚本默认优先使用 `3000`（Web）和 `8010`（API）；端口占用时会自动选择可用端口，并同步前端 API 地址。

输出中的 `Website: http://127.0.0.1:<port>` 为浏览器入口。保持启动窗口打开，按 `Ctrl+C` 可同时停止前后端。

要使用前端热更新：

```bash
ZAOJING_WEB_MODE=dev uv run python scripts/start_local.py
```

## 手动启动

后端：

```bash
cd apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
```

前端：

```bash
cd apps/web
npm run dev -- --hostname 127.0.0.1 --port 3000
```

浏览器中的 HTTP 与 WebSocket 都直接访问 `http://127.0.0.1:8010`，不经过 Next.js `/api` 代理。

## 常用配置

| 环境变量 | 用途 |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | 前端 HTTP API 地址 |
| `NEXT_PUBLIC_API_WS_URL` | 前端 WebSocket 基址（仅特殊部署需要） |
| `CODEX_BINARY` | Codex App Server 可执行文件路径 |
| `CODEX_WORKSPACE` | Codex 工作目录 |
| `DATABASE_PATH` | SQLite 数据库路径 |
| `COMFYUI_BASE_URL` | ComfyUI 地址，默认为 `http://127.0.0.1:8000` |
| `ZAOJING_ASSET_DIR` | 本地素材目录 |
| `ZAOJING_SECRET_KEY_PATH` | 凭证加密密钥文件 |

## 验证

后端：

```bash
cd apps/api
uv run pytest -q
uv run ruff check .
```

前端：

```bash
cd apps/web
npm run typecheck
npm run check:architecture
npm test
npm run build
```

启动后端后可运行真实 Codex 链路检查：

```bash
uv run python scripts/check_chat.py
uv run python scripts/check_interrupt.py
```

## 文档索引

- [`AGENTS.md`](AGENTS.md)：规范工程契约
- [`docs/backend-architecture.md`](docs/backend-architecture.md)：后端架构与依赖边界
- [`docs/frontend-architecture.md`](docs/frontend-architecture.md)：前端功能与依赖边界
- [`docs/sqlite-schema.md`](docs/sqlite-schema.md)：数据库结构
- [`docs/multi-model-gateway-design.md`](docs/multi-model-gateway-design.md)：多模型网关设计
- [`docs/creative-agent-workflow-design-v2.md`](docs/creative-agent-workflow-design-v2.md)：创作 Agent 工作流设计
- [`docs/codex-app-server.md`](docs/codex-app-server.md)：Codex协议集成说明
- [`apps/api/README.md`](apps/api/README.md)：API启动、接口与排查
- [`apps/web/README.md`](apps/web/README.md)：Web端开发与会话协议
