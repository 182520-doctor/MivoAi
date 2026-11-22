# 造境前端模块架构

日期：2026-11-22

## 目标

前端按功能和业务职责拆分，避免所有状态、API、SSE 解析和界面继续集中在单个
`page.tsx`。当前不引入额外状态库，继续使用 React 原生状态和 Hook。

## 目录结构

```text
apps/web/app
├── page.tsx
├── chat/page.tsx
├── media/page.tsx
├── drama/page.tsx
├── assets/page.tsx
├── tasks/page.tsx
├── _features
│   ├── chat
│   │   ├── api.ts
│   │   ├── streamReducer.ts
│   │   ├── types.ts
│   │   ├── useChatSession.ts
│   │   └── useConversationList.ts
│   ├── health
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── useHealthStatus.ts
│   └── models
│       ├── api.ts
│       ├── types.ts
│       └── useModelSettings.ts
├── _components
│   ├── shell
│   ├── media
│   ├── drama
│   ├── assets
│   ├── tasks
│   ├── chat
│   ├── conversation
│   ├── home
│   └── workspace
└── _shared
    └── api
```

## 信息架构

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/` | 工作台总览，明确两个产品方向 | 可用 |
| `/chat` | Agent 对话与创意梳理 | 可用 |
| `/media` | 图片、视频、音频处理与任务结果 | 可用 |
| `/drama` | 短剧从剧本到成片的导演工作台 | 可用 |
| `/models` | 模型目录、ComfyUI 工作流扫描/导入/测试、默认模型 | 可用 |
| `/assets` | 素材库、类型筛选与关键词检索 | 可用 |
| `/tasks` | 统一任务中心、状态筛选与关键词检索 | 可用 |

左侧导航按“工作台、创作、管理”分组，并使用深色制作导航与独立的新建创作入口。
移动端切换为底部导航，但保留完整文字标签，避免只显示图标导致页面含义不清。

`StudioFrame` 提供全局侧栏和连接状态；`StudioMain` 区域只渲染当前路由页面。
未连通的能力必须明确显示“待接入”或“设计预览”，不能显示为可执行成功状态。

## 职责边界

### `_features`

拥有功能用例和浏览器数据逻辑：

- 调用 `/api`；
- 解析 SSE；
- 转换服务端事件；
- 管理功能状态；
- 提供会话发送、停止、历史加载、模型配置和健康检查 Hook。

功能模块不负责复杂页面布局。

### `_components`

拥有展示组件：

- `StudioFrame`、`AppSidebar`：产品壳和清晰导航；
- `WorkspaceShell`：组合各功能 Hook 和页面区域；
- `HistoryDrawer`：会话历史；
- `ModelSettingsDrawer`：模型选择和凭证配置；
- `Composer`：输入框及发送/停止操作；
- `MessageList`、`ReasoningPanel`：消息和思考过程；
- `HomeView`、`ChatView`：首页和聊天模式。

组件通过 Props 接收状态和操作，不直接拼装供应商请求。

### `_shared`

仅放跨功能通用能力。目前包括 JSON HTTP 客户端。业务类型和接口不放入
`_shared`，避免形成新的公共杂物目录。

## Server / Client 边界

- `app/page.tsx` 保持 Server Component，只渲染 `WorkspaceShell`；
- `WorkspaceShell` 是 Client Component，建立交互和浏览器状态边界；
- Hook 使用 `localStorage`、`fetch`、`AbortController` 和流式读取；
- 前端只访问同源 `/api`，不直接访问 FastAPI、Codex 或 ComfyUI。

## 会话数据流

```text
Composer
  -> useChatSession.sendMessage
  -> features/chat/api.streamMessage
  -> FastAPI SSE
  -> streamReducer.applyServerEvent
  -> useChatSession messages
  -> MessageList / ReasoningPanel
```

任务事实仍来自后端 SQLite。前端消息状态只负责当前流式交互，刷新或重新打开会话时以
`GET /api/conversations/{id}/messages` 为准。

API 启动时会扫描遗留的 `running` turn 和 `streaming` assistant message。无法续接的
内存 SSE 会被收敛为 `interrupted`，保留已经生成的部分文本并提示“可重新发送”；
真实请求失败仍使用红色 `error`，两者不再混为同一个 `network error`。

分集画布使用 `GET /api/drama/projects/episodes/{id}/audit` 展示本集质量条。分数、
阻断错误、警告和前三项具体问题直接来自后端领域审计；Agent 修复入口会携带同一批
问题进入对话，但不会自动审批或启动批量生成。

## 状态拆分

- `useHealthStatus`：每 5 秒检查本地 Codex 连接；
- `useModelSettings`：模型目录、默认模型、API Key 表单和保存状态；
- `useConversationList`：左侧会话列表；
- `useChatSession`：输入、消息、当前会话、SSE、停止和推理展开。

各 Hook 之间通过 `WorkspaceShell` 组合，不通过全局单例共享状态。

Codex 的在线状态以 App Server 进程是否运行且 `/api/status` 返回 `ok` 为准。
当前本地 App Server 的 `account/read` 可能返回空账号，但已加载环境中的 Codex
凭据仍能正常执行会话；因此不能把 `authenticated=false` 等同于服务不可用。
如需展示账号态，应作为独立的只读诊断信息，而不是禁用发送按钮。

## 后续媒体与短剧模块

新增功能应继续按域拆分：

```text
_features/media-tasks
_features/assets
_features/drama
_features/production
```

对应页面组件放在：

```text
_components/media
_components/drama
_components/production
```

媒体任务模块负责生成任务 API、SSE 和候选结果状态；短剧模块负责剧本、故事圣经、
拆解和审批；生产模块负责任务编排和时间线。不要把 ComfyUI 节点参数或供应商协议放入
通用 UI 组件。

短剧资产绑定统一经过持久候选账本。`DramaCandidateHistory` 负责首帧、尾帧、九宫格、
故事板和镜头视频的候选浏览、重新选择和弃用；实体专业槽位在卡片内直接显示历史候选
选择器。前端只使用语义槽位和候选 ID，不依赖具体 ComfyUI 节点。

`DramaProductionRunPanel` 放在制作控制室中展示批量任务图。启动和失败项重试由用户点击
确认，运行过程中轮询持久状态；成功项和已绑定素材不会因部分失败被覆盖。

制作阶段采用 episode-first 布局：资产、分镜、镜头视频和时间线不再先渲染通用阶段
说明与完整控制室。分镜默认显示本集视觉板，上方固定本集资产架和 AI 编排入口，选中
片段后进入精细编辑；质量门和角色审核收进页面底部折叠抽屉。

镜头提示词作为正式制作数据保存在 `promptOverrides`，不是 textarea 临时状态。
首帧、尾帧、九宫格、故事板、视频和音频槽位各自独立保存，并在生成前自动落库。
实体专业槽位同样保存 `assetPrompts`，资产页可直接查看、编辑并生成前自动保存。
分镜板卡片提供镜头级审核状态：用户可“通过此镜”或“退回复做”，新视频会自动撤销
上一版的镜头批准。

## 样式

当前 `globals.css` 保留为统一视觉样式，组件拆分不改变现有 class 名称和布局。后续样式
变大时，可以按 `base / workspace / conversation / media / drama` 拆成独立全局样式文件，
但应继续保持统一设计变量。

UI 2.0 使用统一的纸面背景、深色导航、电影化双工作台入口、16–22px 卡片圆角与
低对比光晕。页面标题、状态标签、控件和媒体预览共享同一套层级规则。素材库和任务中心
的筛选栏在浏览器中直接驱动客户端数据，不向 API 重复发送无意义查询。

短剧页面的全局层采用 `DramaCanvasBoard`：默认展示剧本、分集拆解、资产、镜头和后期
五条关系链；支持拖动平移、缩放、复位和节点属性检查器。点击“进入详细编辑”后才进入
对应阶段，顶部使用剧本、制作资产库、分镜三个主阶段，子阶段在内容区切换。短剧 Agent
栏改为右侧真实 `DramaAgentPanel`，通过 `useChatSession` 使用项目、分集或阶段独立的
thread key；中间区域只显示当前所选范围的实时结果，窄屏下 Agent 面板移动到下方。

`DramaScriptWorkspace` 将剧本阶段从原始 textarea 改为阅读优先工作区：集目录、
故事设定、分集大纲、剧本正文、编辑/阅读切换、字数与预计时长、审批状态和下一步动作
均由现有文档聚合派生。右侧 `DramaAgentPanel` 在长文档滚动时保持固定可见。

多模态工作台按真实能力分为图片、视频、音频三个模式。音频模式使用
`audio_processing` 工作流，能够展示多轨播放器，并根据结果素材的文件名把通用轨道编号
映射为人声、鼓、贝斯和其他轨道。任务详情通过安全素材摘要返回名称、MIME、大小和 URL，
不把本地文件路径传到浏览器。

视频模式同时发现 `video_generation` 与 `video_processing` 模型，但提交任务时保留真实
类型：抠像、补帧等确定性变换使用 `video_processing`，生成模型使用
`video_generation`。模型选择器统一面向用户，底层任务语义不混用。

短剧镜头声音面板提供“转写字幕并加入本集”。前端会把镜头音频的转写 cue 按镜头在分集
中的时间偏移换算到整集时间轴，与已有字幕合并、去重并排序后保存。

## 验证

```powershell
cd apps/web
.\node_modules\.bin\tsc.cmd --noEmit
node node_modules\next\dist\bin\next build
```

`pnpm typecheck` 在依赖安装完整时同样可用。当前环境曾因 npm registry 下载超时导致
`pnpm` 自动安装检查失败，但现有依赖下的 TypeScript 检查和生产构建均已通过。

本轮额外使用真实 Chrome 和 Playwright 验收：

- 8 个路由 × 1440 / 1024 / 768 / 390 四档宽度，共 32 个页面状态；
- 所有页面均无水平溢出；
- 无失败 HTTP 请求和浏览器运行时错误；
- 素材类型/关键词筛选、任务状态/关键词组合筛选均通过真实交互验证。
