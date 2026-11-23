<div align="center">

# MivoAi · 造境

### 面向复杂创作的 Agent 驱动多模态生产平台

**从一句模糊创意，到故事结构、剧本、分镜、图片、视频与最终资产，MivoAi 正在构建一个可持续工作、可审查、可回溯的创作工程系统。**

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**文本创作 · 剧本工作流 · 模型路由 · ComfyUI 生产 · 素材资产 · 长期记忆**

</div>

---

## 为什么是 MivoAi

��统生成工具擅长“一次回答”；真正的内容生产却是一条持续演进的工程链路：

```text
创意构思
  → 故事设定与人物世界
  → 剧本、分集与场景
  → 分镜、视觉提示词与参考资产
  → 图片、视频、配音与字幕
  → 剪辑、成片、修改、回溯与再次发布
```

MivoAi 的目标不是把模型变成聊天框，而是建立一套可持续工作的创作基础设施：

- **作品不是聊天记录**：项目、设定、产物版本和工作流状态均可持久保存。
- **Agent 不是孤立模型**：Agent 在项目工作空间、领域规则和可审计工作流中协作。
- **产物不是一次性文本**：剧本、角色、场景、分镜、素材和任务形成可追踪生产链路。
- **修改不是从零重写**：稳定实体、产物版本和影响范围用于保持前后连续性。
- **模型不是唯一后端**：Codex、本地或远程供应商、ComfyUI、FFmpeg 和 TTS 按能力协作。

> MivoAi 的长期愿景，是成为从创意到成片的通用创作操作系统：用户表达意图并审定关键决策，Agent负责拆解、执行、校验和持续推进。

---

## 创作视觉

仓库中已包含前端灵感与场景演示资源：

<p align="center">
  <img src="apps/web/public/inspiration-grid.png" alt="MivoAi 灵感画廊" width="49%" />
  <img src="apps/web/public/demo-city.png" alt="MivoAi 城市场景演示" width="49%" />
</p>

- 灵感画廊用于集中浏览视觉参考，服务创作发散与素材采样。
- 场景演示用于验证画面、氛围和多模态创作流程。

当前可运行的主链路是：**创作对话 → 创作项目 → 项目工作空间 → Agent 自动执行 → SQLite产物与流程状态 → 前端同步展示**。

---

## 核心能力

<table>
<tr>
<td width="50%" valign="top">

### Agent 创作协作

- 多轮流式对话与服务重启后的会话恢复
- 可折叠展示公开 reasoning 与推理 token
- 中止正在生成的回合
- 项目专属工作目录与 Codex Thread
- 创作项目创建后自动启动 Agent
- WebSocket 推送公开进度与项目同步事件

</td>
<td width="50%" valign="top">

### 创作工程内核

- 项目、工作空间、工作流与产物分离
- 创作产物版本与变更哈希
- SQLite 保存项目、节点、产物和执行记录
- 工作流模板、节点运行与步骤状态
- 文件扫描、产物同步与项目状态更新
- 数据库事实源与可移植工作空间双轨管理

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 多模态生产

- 本地 ComfyUI 工作流发现与导入
- 工作流 JSON 到 API 图转换
- Flux 文生图与 Wan 文生视频
- 模型目录、能力筛选与启用管理
- 生成任务、进度、结果与素材闭环
- 火山方舟文本与多模态接口接入

</td>
<td width="50%" valign="top">

### 模型与供应商

- Provider / Model 目录与偏好设置
- 页面内配置供应商凭证
- 凭证加密保存与密文保护
- 文本路由、媒体适配与真实连接测试
- 模型能力筛选与默认模型切换
- 生成请求与审计记录持久化

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 剧本与短剧工作流

- 小说、剧本、分集、场次与镜头结构
- 故事圣经、人物、地点、道具与伏笔规划
- 项目、系列、分集、场景、镜头内容树
- 草案、审核、正式产物与影响分析
- 长期连续性、时长预算与质量门禁
- 从文本创作自然扩展到分镜与成片

</td>
<td width="50%" valign="top">

### 桌面与移动工作台

- Next.js App Router + React + TypeScript
- 桌面端与移动端自适应界面
- GFM Markdown、表格、列表与代码块
- 会话导航、模型中心与灵感展示
- 功能域、Widget、共享层清晰分离
- HTTP / WebSocket 直接访问 FastAPI

</td>
</tr>
</table>

---

## 从创意到成片

MivoAi 的目标工作流分为多个可审核、可恢复的阶段：

```text
用户创意
  │
  ├─ 创意简报与方向提案
  ├─ 故事圣经与人物设定
  ├─ 全季结构与分集大纲
  ├─ 场景、对白与完整剧本
  ├─ 连续性、时长与叙事质量检查
  │
  ├─ 分镜与镜头语言
  ├─ 角色、服装、场景与道具视觉参考
  ├─ 文生图 / 图生图提示词与任务
  ├─ 文生视频 / 图生视频提示词与任务
  │
  └─ 配音、字幕、剪辑、素材管理与成片导出
```

草案可以迭代，关键设定可以审批，正式版本可以追溯来源，受影响内容可以按范围更新，而不是无差别重写整个作品。

---

## 系统架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                         MivoAi 工作台                            │
│       Next.js / React / TypeScript / WebSocket / REST            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI 应用                             │
│            会话 · 项目 · 工作流 · 模型 · 媒体 · 素材              │
├──────────────────────────────┬──────────────────────────────────┤
│       conversations          │       creative_projects          │
│       drama                  │       providers                  │
│       workflows              │       media_generation           │
│       assets                 │       media_processing           │
└──────────────┬───────────────┴──────────────────────────────────┘
               │
       ┌───────┴────────────────────────┐
       ▼                                ▼
┌─────────────────┐            ┌─────────────────────┐
│  Codex          │            │  多模型与多模态栈   │
│  App Server     │            │  火山方舟 / ComfyUI │
│  stdio JSON-RPC │            │  FFmpeg / TTS       │
└────────┬────────┘            └──────────┬──────────┘
         │                                │
         ▼                                ▼
  Agent Thread / Turn              图片、视频、音频与素材任务

         ┌─────────────────────────────────────────────┐
         │ SQLite：项目、产物、版本、任务与审计事实源 │
         │ Workspace：可移植、可阅读、可恢复的项目文件 │
         └─────────────────────────────────────────────┘
```

这是一个本地模块化单体，不拆分为微服务。后端采用领域模块优先的 DDD 分层：

```text
apps/api/app/
├── modules/
│   ├── conversations/       对话、Agent运行时与流式回复
│   ├── creative_projects/   创作项目、工作空间与产物版本
│   ├── drama/               剧集、场次、镜头与生产运行
│   ├── providers/           模型供应商、凭证与文本路由
│   ├── workflows/           ComfyUI工作流与模型注册
│   ├── media_generation/    图片、视频生成任务与状态
│   ├── assets/              素材登记、读取与内容访问
│   └── media_processing/    FFmpeg、TTS、字幕与媒体处理
├── delivery/                 HTTP API与Agent工具适配
├── adapters/                 SQLite、Codex、ComfyUI与外部服务
├── shared/                   配置、安全、错误与公共基础设施
├── composition.py            依赖装配入口
└── main.py                   FastAPI应用入口
```

前端按功能域组织：

```text
apps/web/
├── app/                      路由、布局与全局样式
├── features/chat/            会话与流式协议
├── features/creative-projects/ 创作项目与工作区
├── features/models/          模型与供应商配置
├── features/inspiration/     灵感与参考展示
├── features/system/          后端运行状态
├── widgets/workspace/        页面级工作台组合
└── shared/                   通用API与UI基础设施
```

工程约束以 [`AGENTS.md`](AGENTS.md) 为准。

---

## 仓库结构

```text
apps/
├── api/              FastAPI、领域模块与基础设施适配器
└── web/              Next.js App Router 与 React 工作台

docs/                 架构、协议、数据库与集成文档
scripts/              本地启动与真实链路检查
vendor/codex/         本地Codex运行时与协议资源
```

---

## 快速开始

### 环境要求

- Python 3.12+
- `uv`
- Node.js 与 npm/pnpm
- 可选：本地 ComfyUI
- 可选：已登录或已配置的 Codex CLI
- 可选：FFmpeg

### 一键启动

在仓库根目录运行：

```bash
uv run python scripts/start_local.py
```

启动脚本默认使用 `3000` 与 `8010`。端口被占用时会选择可用端口并同步前端 API 地址。

看到：

```text
Website: http://127.0.0.1:<port>
```

即可在浏览器中打开工作台。

需要前端热更新：

```bash
ZAOJING_WEB_MODE=dev uv run python scripts/start_local.py
```

按 `Ctrl+C` 可同时停止前后端。

### 手动启动

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

ComfyUI 默认端口为 `8000`，MivoAi API 默认端口为 `8010`。

浏览器中的 HTTP 与 WebSocket 都直接访问 FastAPI，不经过 Next.js `/api` 代理。

---

## 常用配置

| 环境变量 | 用途 |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器访问的 FastAPI 地址 |
| `NEXT_PUBLIC_API_WS_URL` | WebSocket 基址；特殊部署时覆盖默认值 |
| `CODEX_BINARY` | 本地 Codex App Server 可执行文件 |
| `CODEX_WORKSPACE` | Codex 默认工作目录 |
| `DATABASE_PATH` | SQLite 数据库路径 |
| `COMFYUI_BASE_URL` | ComfyUI 地址，默认 `http://127.0.0.1:8000` |
| `ZAOJING_ASSET_DIR` | 素材与生成结果存储目录 |
| `ZAOJING_SECRET_KEY_PATH` | 凭证加密密钥文件 |
| `CODEX_PROTOCOL_LOG` | 是否启用 Codex 协议日志 |

协议日志默认保存于 `runtime/logs/codex-protocol.log`；账号、Token、密码和密钥字段会在输出前脱敏。

---

## 验证与开发

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

查看实时 Codex 协议：

```bash
tail -f runtime/logs/codex-protocol.log
```

---

## 路线图

### 已落地

- [x] Codex Agent 对话、流式输出与中断
- [x] 项目工作空间与项目专属 Thread
- [x] 创作项目创建后自动启动 Agent
- [x] SQLite 会话、产物和工作流状态
- [x] 产物文件变化扫描与版本同步
- [x] 多供应商目录、凭证和模型偏好
- [x] 本地 ComfyUI 工作流发现与转换
- [x] Flux 文生图与 Wan 文生视频任务
- [x] 生成任务、进度与素材登记闭环
- [x] 桌面端与移动端响应式工作台

### 正在建设

- [ ] 完整结构化剧本、场景与角色 Schema
- [ ] 故事实体、连续性事实与伏笔回收检查
- [ ] 分集、场次、镜头与工作流审批状态
- [ ] 用户修改后的影响分析与局部重写
- [ ] 审核、正式发布、回滚与分支版本
- [ ] Skill 注册、版本锁定与显式调用
- [ ] SQLite FTS / 知识检索与候选审批

### 未来方向

- [ ] 小说、广告、短片、短剧领域包
- [ ] 分镜、角色一致性与视觉参考资产
- [ ] 图生图、图生视频与视频二次编辑
- [ ] 配音、音乐、字幕、剪辑与时间线
- [ ] 质量评测、用户反馈与受控知识增长
- [ ] 长任务队列、断点恢复与后台生产
- [ ] 多模型协作、专业审查 Agent 与人工审批
- [ ] 从本地创作工作站走向可部署协作平台

当前明确不将 Codex Thread 当作唯一项目记忆，不用聊天记录替代结构化事实，也不允许 Agent绕过版本与质量规则直接覆盖正式产物。

---

## 文档

- [`docs/creative-agent-workflow-design-v2.md`](docs/creative-agent-workflow-design-v2.md) — 通用创作 Agent 工作流愿景与设计
- [`docs/creative-agent-implementation-status.md`](docs/creative-agent-implementation-status.md) — 创作项目当前实现状态
- [`docs/director-agent-workflow.md`](docs/director-agent-workflow.md) — 导演 Agent 文本工作流
- [`docs/backend-architecture.md`](docs/backend-architecture.md) — 后端架构与模块边界
- [`docs/sqlite-schema.md`](docs/sqlite-schema.md) — SQLite 数据结构
- [`docs/multi-model-gateway-design.md`](docs/multi-model-gateway-design.md) — 多模型网关设计
- [`docs/codex-app-server.md`](docs/codex-app-server.md) — Codex App Server 协议集成
- [`apps/api/README.md`](apps/api/README.md) — API 启动与接口文档
- [`apps/web/README.md`](apps/web/README.md) — Web 工作台开发说明

---

<div align="center">

**MivoAi — 让创意进入一个可执行、可验证、可持续演进的生产系统。**

</div>
