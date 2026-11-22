# 造境后端 DDD 架构

日期：2026-11-22

> 工程强制规范以根目录 [`AGENTS.md`](../AGENTS.md) 为准。本文说明架构背景和
> 请求流程；新增代码必须遵循 `AGENTS.md` 中的目录和依赖约束。

## 设计目标

后端采用**限界上下文优先的模块化单体**。每个业务模块独立维护自己的 HTTP Schema、应用用例、领域对象、端口和基础设施适配器；会话、生成任务、供应商路由与素材不再共享一个业务服务或 Repository。

当前仍保持：

- 单一 FastAPI 进程；
- 单一 SQLite 数据库；
- 本地 Codex App Server；
- 现有 HTTP 路径和前端行为不变。

## 目录结构

```text
apps/api/app
├── modules
│   └── <domain>
│       ├── domain.py
│       ├── application.py
│       ├── commands.py
│       ├── ports.py
├── delivery
│   ├── http
│   │   ├── api.py
│   │   ├── routes
│   │   ├── schemas
│   │   └── errors.py
│   └── agent
├── adapters
│   ├── persistence
│   │   ├── database.py
│   │   └── sqlite
│   ├── codex
│   ├── comfyui
│   ├── providers
│   ├── media
│   └── workspaces
├── shared
├── composition.py
└── main.py
```

## 限界上下文

### Conversations

负责：

- 会话、Turn、Message 持久化；
- Codex Thread 与本地会话的关联；
- Agent 流式事件、推理内容和中止；
- 通过 `ConversationModelGateway` 端口选择文本模型；
- 通过 `ConversationTaskRecorder` 端口记录文本生成任务；
- 通过 `CodexClient` 端口调用本地 Agent 运行时。

该上下文不知道火山方舟、生成任务表或素材文件实现。

### Providers

负责：

- Provider、Model、Credential 和用户偏好；
- 文本模型与媒体模型路由；
- 供应商能力检查；
- 凭证解密和外部请求执行；
- 火山方舟文本和媒体 Adapter；
- 将供应商协议隔离在 `infrastructure`。

该上下文不管理会话历史、任务状态和素材内容。

### Media Generation

负责：

- 统一 `GenerationTask` 生命周期；
- 图片与视频任务创建、进度、失败和结果资产 ID；
- 文本任务审计记录的创建和完成；
- 通过 `MediaModelResolver` 解析模型；
- 通过 `MediaProviderGateway` 执行供应商请求；
- 通过 `GeneratedAssetIngestor` 保存结果素材。

该上下文不写会话消息，也不实现具体供应商协议。

### Media Processing

负责不需要模型推理的确定性媒体操作：

- 视频音轨提取与标准化；
- 后续视频抽帧、拼接、转场、混音和成片导出；
- 通过端口调用 FFmpeg，不把子进程细节泄漏到短剧或素材模块。

当前已实现 `POST /api/media/processing/extract-audio`。处理结果通过素材
上下文的本地入库端口登记，返回的 `assetId` 可由短剧镜头持久化引用。

整集合成由短剧上下文的渲染端口触发。`MediaProcessingService` 负责解析视频
素材路径、调用 FFmpeg 统一画幅/帧率/音频并入库；短剧上下文只保存返回的
`exportAssetId`，不依赖 FFmpeg 或素材仓储内部实现。

离线 TTS 同样通过媒体处理端口接入。当前 Windows 适配器调用
`System.Speech` 生成 48 kHz WAV；Qwen3-TTS 因依赖版本与 ComfyUI 主环境冲突，
后续应作为独立 worker 进程接入，而不是合并 Python 环境。

### Assets

负责：

- 生成结果的本地文件落盘；
- 素材元数据登记；
- 素材内容读取；
- 远程结果下载适配器。

后续可在这里替换为对象存储，不影响生成任务和会话模块。

### System

负责健康检查和旧接口迁移提示。

## 依赖规则

```text
routes
  -> application
  -> domain / ports

composition
  -> concrete repositories
  -> concrete adapters
  -> application services
```

- `domain.py` 不依赖 FastAPI、SQLite、httpx、Starlette 或 Uvicorn；
- `ports.py` 只定义 Protocol 和共享值对象；
- `application.py` 接收 `commands.py` 中的应用命令，不依赖 HTTP Schema；
- `application.py` 只依赖本上下文 command、domain、ports 和 shared；
- `infrastructure` 实现 Repository、Adapter 和下载器；
- `routes` 不写 SQL，不访问外部供应商；
- 跨上下文只通过公开应用方法或 Protocol 交互；
- 禁止导入其他上下文的 Repository 或 Infrastructure；
- `composition.py` 是唯一依赖装配入口；
- `main.py` 只注册路由和生命周期。

当前 SQLite 仍是单一物理数据库，因此建表和索引集中在
`adapters/persistence/database.py`。业务查询已经按领域模块拆到独立
Repository；后续如果某个模块迁移到独立数据库，只需把对应建表和迁移随上下文一起移走。

`tests/test_architecture.py` 会检查：

- Application、Domain、Ports 不导入本上下文 Infrastructure；
- Application 不导入 HTTP Schema；
- Domain、Ports 不导入 Web 框架、SQLite 或 HTTP 客户端；
- 一个上下文不直接导入另一个上下文的 Repository 或 Infrastructure。

## 新会话请求流程

1. `delivery/http/routes/conversations.py` 验证 `MessageCreate`。
2. `ConversationService` 检查会话、并发和幂等提交。
3. `ConversationRepository` 原子创建 Turn、用户消息和助手占位消息。
4. `ConversationModelGateway` 返回 `TextModelRoute`。
5. `ConversationTaskRecorder` 在发送外部请求前创建文本生成任务。
6. 本地 Codex 使用 `CodexClient`；HTTP 模型通过 Provider 端口流式返回。
7. Conversation Service 一边写入消息和推理内容，一边向 SSE 队列发送事件。
8. 无论完成、失败或中止，统一完成 Turn 和任务审计记录。

## 媒体生成流程

1. `delivery/http/routes/media_generation.py` 接收 `GenerationCreate`。
2. `GenerationService` 通过 `MediaModelResolver` 校验 Provider、模型和能力。
3. `GenerationTaskRepository` 先落任务，再启动后台执行。
4. `MediaProviderGateway` 调用当前供应商 Adapter。
5. 远程结果通过 `AssetService` 下载并登记。
6. 资产 ID 写回任务，任务状态和事件同步更新。

## 扩展方式

### 增加供应商

1. 在 `providers/infrastructure` 实现 Adapter；
2. 在 `providers/ports.py` 增加必要端口；
3. 在 `providers/application.py` 增加能力路由；
4. 在 `composition.py` 注入实现；
5. 不修改会话、素材和任务 Repository。

### 增加 ComfyUI

1. 新增 `adapters/comfyui/` 适配器；
2. 实现提交、状态、取消和结果下载；
3. 通过 `MediaProviderGateway` 路由到 ComfyUI；
4. 素材仍由 Asset 上下文登记；
5. Workflow 模板和任务运行记录后续作为独立 `workflow_runtime` 上下文加入。

### 增加短剧模块

`modules/drama` 拥有：

- Drama Project；
- Story Bible；
- Script Version；
- Scene Plan；
- Shot；
- Timeline；
- Production Run。

短剧模块只通过 `media_generation` 的公开用例提交生成请求，不直接访问 ComfyUI。

### 替换数据库

保持应用端口不变，在 `adapters/persistence` 增加 PostgreSQL Repository
实现，并在 `composition.py` 替换即可。视频异步任务开始使用独立 Worker
时，应继续复用 `GenerationTaskRepositoryPort`。

## 验证命令

```powershell
cd apps/api
uv run pytest -q
uv run ruff check app tests
uv run python -m compileall -q app tests
```
