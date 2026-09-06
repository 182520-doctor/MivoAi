# 造境多模型统一接入系统设计文档

版本：v1.3（统一任务审计模型修订）  
日期：2026-09-06  
适用项目：`work/ai-dev-starter`

## 1. 背景与目标

当前造境 Agent MVP 已经具备本地会话、SQLite 历史、Markdown 消息和 Codex App Server 接入能力。下一步把它扩展为一个模型网关：前端只有一个统一入口，用户可以选择供应商、能力类型和具体模型；后端负责屏蔽供应商 API 差异，并把文本、图片、视频和多模态调用统一成可追踪、可审计的任务模型。

当前真实测试继续使用已有的本地 Codex App Server 链路：浏览器 → FastAPI → 本地 Codex 子进程（stdio / JSON-RPC）。沿用现有本地认证，不要求用户为了本阶段测试购买第三方 API Key。Mock 仅用于图片、视频任务和故障的自动化测试，不替代当前真实 Agent。真实图片、视频供应商在后续阶段按同一套接口接入。SQLite 继续作为 MVP 的事实来源。

开源交付目标：用户自行部署后，在页面选择已经适配的供应商、输入自己的 API Key、验证连接并选择模型，即可使用相应能力。官方服务预填 API 地址；兼容平台允许修改 Base URL。部分供应商还需区域、项目或推理接入点 ID，由对应表单提示。填写 Key 不代表所有供应商协议天然兼容，也不代表账号已开通所有模型。

本轮明确记录的待办：当前后端已经产生 SSE 增量事件，前端也有增量读取逻辑，但当前验收现象是页面可能只看到最终结果，Codex 思考和回复过程的可见流式展示仍需单独修复。修复时要分别检查 App Server 是否产生增量事件、FastAPI 是否及时 flush、浏览器是否逐事件读取，以及 React 是否增量更新。SSE 支持持续增量推送和断线重连；取消可以通过现有 POST 接口实现，这些需求本身不需要改成 WebSocket。

### 1.1 当前实现基线与验收边界

当前代码可以验收的真实能力如下：

- 浏览器通过 Next.js 同源接口访问 FastAPI。
- FastAPI 通过 stdio / JSON-RPC 连接本机 Codex App Server。
- 本地 Codex 使用本机已有登录状态，当前 Agent 对话不依赖第三方 API Key。
- SQLite 中的 `sessions`、`turns`、`messages` 和 `submissions` 是页面会话历史的来源；页面不读取 Codex 本地会话历史作为产品历史。
- 已有 Markdown、reasoning 折叠、停止回复和 Codex 协议日志能力。

以下能力属于本设计的目标实现，目前不能视为已经完成：`model_providers`、`provider_credentials`、`models`、`user_preferences`、`generation_tasks`、`assets`、`task_events`，以及外部供应商的真实 HTTP 适配器。

当前测试的通过标准是：不填写任何第三方 Key，仍能通过本地 Codex 完成对话、落 SQLite、刷新后恢复历史，并能检查 Codex 与后端之间的脱敏 JSON-RPC 日志。外部 API Key 配置和图片/视频生成要在对应阶段单独验收，不能用 Mock 结果宣称供应商已经接通。

## 2. 总体架构

```text
浏览器
  |
  | REST: 会话、模型、偏好、任务、素材
  | SSE: 文本增量、任务状态、结果事件
  v
FastAPI API 层
  |
  v
应用服务层
  |- ConversationService  对话与 Codex Agent
  |- ModelCatalogService  供应商、模型、用户可用范围
  |- GenerationService    统一生成任务生命周期
  |- AssetService         上传、下载、转存和访问地址
  |- PreferenceService    用户偏好
  |
  v
模型网关层
  |- ProviderAdapter 接口
  |- CodexAdapter
  |- MockAdapter
  |- OpenAICompatibleAdapter
  |- VolcengineAdapter（后续）
  |- BailianAdapter（后续）
  |- MiniMaxAdapter（后续）
  |
  +--> SQLite Repository --> sessions/tasks/assets/events
  +--> 本地文件存储 data/assets
  +--> 外部模型 HTTP API
```

目录建议：

```text
apps/api/app
├── api/routes/              HTTP 路由
├── core/                    配置、异常、接口、日志
├── db/                      连接、迁移、Repository
├── models/                  请求模型和领域模型
├── services/                用例编排
├── gateway/                 ProviderAdapter 和统一模型调用
│   ├── contracts.py
│   ├── registry.py
│   └── adapters/
└── utils/                   SSE、文件名、时间、JSON 等纯工具
```

路由不直接调用供应商、不写 SQL。Provider 适配器不感知 FastAPI 和前端字段。Service 负责事务、权限、任务状态和事件落库。

## 3. 核心领域模型

### 3.1 Provider 与 Model

`Provider` 是一个供应商连接实例，可分别配置官方平台和多个兼容中转平台；`adapter_key` 指定 `volcengine`、`bailian`、`minimax`、`openai_compatible`、`codex_local` 或 `mock` 适配器。`Model` 是实例下面的具体模型，保存实际 API 模型 ID 或接入点 ID。用户举例的 Seedance 等名称仅作为需求示例，具体版本、能力和开放情况须在真实适配时核实，不预置未经验证的可用模型。

开源版本采用“适配器 + 用户凭证”模式：平台代码只内置供应商协议和默认地址，不内置平台运营方的 API Key。用户在自己的部署实例中填写自己的 Key、Base URL、区域、项目或接入点等配置；服务端根据 `provider_id` 和 `model_id` 选择适配器，并把凭证注入供应商请求。仅填写 Key 不会自动获得供应商权限，也不会让一个供应商的 Key 兼容另一个供应商的协议。

Codex 本地连接属于 `codex_local`，使用已有进程与认证配置；HTTP 供应商属于 `api_key` 认证模式，凭证由网关读取。外部 Key 不会自动改变本地 Codex 的模型或认证。当前 Agent 编排继续使用本地 Codex，第三方图像、视频模型作为工具能力接入；第三方文本对话与完整 Agent 工具循环分别验收。前端选择器只有在服务端完成真实 provider/model 路由后才代表切换成功；在此之前，本地 Codex 仍是当前唯一的真实 Agent 执行后端。

模型必须同时声明能力集合，而不能通过模型名称猜能力：`text`、`image_generation`、`image_edit`、`video_generation`、`video_from_image`、`multimodal_understanding`。每个模型还声明 `sync` 或 `async` 执行方式、支持的输入输出 MIME 类型、参数 schema 和是否启用。

### 3.2 统一能力接口

`generation_tasks` 是所有模型调用的统一持久化单元。文本、图片、视频、多模态、图生图和图生视频都必须先生成任务，再由任务驱动同步返回或异步轮询。`sessions` 只负责工作区、上下文和任务归属，不再作为新网关文本消息的唯一事实来源；`messages` 仅保留为当前 Codex MVP 的兼容层和历史数据层，后续新网关文本结果以任务表为准。

```python
class ProviderAdapter(Protocol):
    async def generate_text(self, request: TextRequest) -> TextResult | StreamResult: ...
    async def generate_image(self, request: ImageRequest) -> GenerationResult: ...
    async def generate_video(self, request: VideoRequest) -> GenerationResult: ...
    async def analyze_image(self, request: ImageAnalysisRequest) -> TextResult: ...
    async def transform_image(self, request: ImageTransformRequest) -> GenerationResult: ...
    async def get_task_status(self, provider_task_id: str) -> ProviderTaskStatus: ...
    async def cancel_task(self, provider_task_id: str) -> None: ...
```

内部统一结果：

- 文本：`TextResult(content, usage, provider_request_id)`，流式文本使用统一事件格式。
- 图片/视频：始终先返回 `GenerationTask`，同步供应商由适配器立即完成任务，异步供应商由后台轮询完成任务。
- 供应商返回 base64、远程 URL 或二进制时，都转换为 `AssetInput`，交给 `AssetService` 统一保存。
- 供应商错误转换为 `ProviderError(code, message, retryable, raw_metadata)`，不把供应商原始错误结构泄漏给前端。

## 4. 前后端交互流程

### 4.1 页面初始化

```text
GET /api/models?capability=text,image_generation,video_generation
GET /api/preferences
GET /api/conversations
```

前端根据模型目录渲染供应商、能力和模型选择器。不可用模型不展示或显示禁用原因。偏好保存后，下次新会话自动使用默认模型。

### 4.2 文本对话

```text
POST /api/conversations/{id}/messages
  -> ConversationService 读取偏好和可用模型
  -> 创建 generation_tasks(task_type=text)
  -> Codex 或文本 Provider
  -> 更新任务状态、结果、provider/model 和脱敏请求快照
  -> SSE 推送 message.delta、message.completed、error
```

Codex 仍然由现有 `ConversationService` 编排，保留既有路由和 SSE 事件名称。默认文本模型必须由服务端实际路由，不能只写入提示词。当前默认执行后端是 `codex_local`；接入外部文本适配器后，普通对话可切换到对应 HTTP 模型。当前 Codex MVP 仍会写入 `turns/messages/submissions` 作为兼容历史，但新统一网关的文本结果以 `generation_tasks` 为准，不再要求单独维护一套长期消息副本。完整第三方 Agent 工具编排需单独实现并标注支持状态，不将普通文本能力显示为完整 Agent 能力。

### 4.3 图片或视频生成

```text
POST /api/generation-tasks
  -> 校验 capability、模型启用状态、用户偏好
  -> 创建 generation_tasks(status=pending)
  -> 选择 ProviderAdapter
  -> 同步结果：直接转存资产并标记 succeeded
  -> 异步结果：保存 provider_task_id，交给轮询器
  -> 返回 task_id

GET /api/generation-tasks/{id}
GET /api/generation-tasks/{id}/events
```

页面先显示任务状态，再通过 SSE 订阅状态变化；刷新页面时直接读取 SQLite，不依赖内存任务列表。

## 5. 数据库设计

所有表使用 UUID 或本地生成的字符串 ID；时间统一保存 UTC ISO 字符串，未来迁移 PostgreSQL 时可改为 `timestamptz`。JSON 字段在 SQLite 使用 TEXT 存储，在 PostgreSQL 使用 JSONB。

### 5.1 `model_providers`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 供应商 ID，如 `volcengine` |
| adapter_key | TEXT | 适配器标识，多实例可共用同一适配器 |
| auth_mode | TEXT | `codex_local/api_key/none` |
| active_credential_id | TEXT FK NULL | 当前选用凭证，必须属于本实例 |
| name | TEXT | 展示名称 |
| kind | TEXT | `builtin`、`openai_compatible`、`custom` |
| base_url | TEXT | API 基地址，可为空 |
| enabled | INTEGER | 是否启用 |
| capabilities_json | TEXT | 供应商能力摘要 |
| created_at / updated_at | TEXT | 时间 |

### 5.2 `provider_credentials`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 凭证 ID |
| provider_id | TEXT FK | 供应商 |
| name | TEXT | 凭证名称 |
| secret_ref | TEXT | 环境变量名或本地密钥引用，不保存明文 API Key |
| secret_source | TEXT | `env/encrypted`，显式指定来源 |
| encrypted_secret | TEXT NULL | 页面输入 Key 的加密密文，env 来源时为空 |
| key_version | INTEGER NULL | 加密主密钥版本 |
| last_verified_at | TEXT NULL | 最近验证成功时间，不代表所有模型可调用 |
| config_json | TEXT | 非敏感配置，如区域、项目 ID |
| enabled | INTEGER | 是否启用 |
| created_at / updated_at | TEXT | 时间 |

页面提供密码输入框，支持保存、替换、删除 API Key 和测试连接。Key 只发送给自己的后端，后端使用成熟加密库的认证加密方案保存密文（例如 Fernet），不自行实现加密。主密钥优先使用部署环境的 `ZAOJING_MASTER_KEY`；本地安装可自动生成到仓库外的用户配置目录，文件权限为 0600，并保持重启稳定。数据库和主密钥需要分别备份；主密钥丢失时须重新输入 Key，不允许静默生成新密钥覆盖。

同时支持环境变量来源，例如 `ZAOJING_OPENAI_API_KEY`。每条凭证明确定义来源，无隐式覆盖；环境来源在页面只展示已配置状态及引用，不能编辑环境变量本身。查询接口仅返回 `configured`、来源和验证状态，永不返回原始 Key 或密文。Key 不进入浏览器持久缓存、Agent 上下文、请求日志、异常详情或配置导出。已被使用的凭证停用保留关联记录，避免破坏任务审计。

### 5.3 `models`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 平台模型 ID |
| provider_id | TEXT FK | 所属供应商 |
| model_key | TEXT | 供应商 API 中的模型名 |
| name | TEXT | 展示名称 |
| capabilities_json | TEXT | 能力列表 |
| execution_mode | TEXT | `sync` 或 `async` |
| input_schema_json / output_schema_json | TEXT | 参数和输出约束 |
| enabled | INTEGER | 是否可用 |
| sort_order | INTEGER | 展示顺序 |
| created_at / updated_at | TEXT | 时间 |
| UNIQUE | provider_id, model_key | 防止重复注册 |

### 5.4 `user_preferences`

单用户 MVP 固定 `user_id=local-user`，保留字段以便以后多用户化。

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | TEXT PK | 用户 |
| default_text_model_id | TEXT | 默认文本模型 |
| default_image_model_id | TEXT | 默认图片模型 |
| default_video_model_id | TEXT | 默认视频模型 |
| allowed_model_ids_json | TEXT | 用户允许 Agent 使用的模型白名单 |
| agent_image_enabled / agent_video_enabled | INTEGER | 是否允许自动调用 |
| style_preference | TEXT | 输出风格 |
| image_settings_json | TEXT | 比例、清晰度、数量 |
| video_settings_json | TEXT | 时长、比例、质量 |
| auto_save_assets | INTEGER | 是否自动保存 |
| updated_at | TEXT | 时间 |

### 5.5 现有会话表

继续使用 `sessions`、`turns`、`messages`，增加可选字段：`default_model_id`、`last_capability`。`sessions` 只作为工作区和任务归属容器，不承担新网关文本历史的唯一存储职责。当前 Codex MVP 仍保留 `turns/messages/submissions` 兼容已有历史；后续页面上的文本历史可以按 `sessions -> generation_tasks` 组装，不必再依赖独立的长生命周期 `messages` 副本。每条 Assistant 消息如需保留 Codex 专用字段，可继续增加 `provider_id`、`model_id`、`metadata_json`。

### 5.6 `generation_tasks`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 平台任务 ID |
| request_id | TEXT UNIQUE | 平台链路追踪 ID，每次服务端实际创建任务时生成 |
| session_id | TEXT FK | 所属会话，可为空 |
| turn_id | TEXT FK | 由 Agent 触发时关联 |
| user_id | TEXT | 用户 |
| provider_id / model_id | TEXT FK | 实际调用目标 |
| credential_id | TEXT FK NULL | 提交时固定的凭证身份，轮询不随当前默认凭证切换 |
| task_type | TEXT | `text`、`image`、`video`、`image_edit`、`video_from_image`、`image_analysis` |
| prompt | TEXT | 用户提示词 |
| original_request_json | TEXT | 用户原始请求，校验通过后、调用供应商前落库 |
| normalized_request_json | TEXT | 服务端补全默认值、能力和参数后的统一请求 |
| provider_request_json | TEXT | 最终发送给供应商的脱敏请求 |
| provider_response_json | TEXT | 供应商返回的脱敏响应摘要 |
| input_asset_ids_json | TEXT | 输入素材 ID 列表 |
| parameters_json | TEXT | 比例、质量等参数 |
| status | TEXT | `pending/running/succeeded/failed/canceled/unknown` |
| progress | INTEGER | 0 到 100，可为空 |
| provider_task_id | TEXT | 供应商任务 ID |
| client_request_id | TEXT UNIQUE | 客户端幂等 ID，防止重复创建 |
| submission_state | TEXT | `not_sent/submitting/accepted/unknown` |
| result_asset_ids_json | TEXT | 结果素材 ID 列表 |
| error_code / error_message | TEXT | 失败信息 |
| retry_count | INTEGER | 重试次数 |
| next_poll_at / deadline_at | TEXT | 下次轮询时间和任务截止时间 |
| lease_owner / lease_expires_at | TEXT | worker 租约，支持重启恢复和避免重复执行 |
| created_at / updated_at / completed_at | TEXT | 时间 |

`generation_tasks` 必须保留三层请求快照：`original_request_json` 保存用户实际提交的业务请求，`normalized_request_json` 保存服务端补全后的统一请求，`provider_request_json` 保存真正发往供应商的脱敏请求。`provider_response_json` 只保留可审计信息，例如任务 ID、状态、错误码、结果 URL 摘要和进度，不保存 API Key、Authorization、Cookie、签名、上传二进制或大体积 base64。`request_id` 用于平台链路追踪，`client_request_id` 用于客户端幂等，两者含义不同。

### 5.7 `assets`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 素材 ID |
| session_id / task_id | TEXT FK | 关联会话和任务 |
| type | TEXT | `image/video/audio/file` |
| source | TEXT | `upload/generated/remote` |
| local_path | TEXT | 本地相对路径 |
| remote_url | TEXT | 原始 URL，可为空 |
| mime_type | TEXT | MIME |
| size | INTEGER | 字节数 |
| width / height | INTEGER | 图片或视频尺寸 |
| duration | REAL | 视频或音频秒数 |
| checksum | TEXT | 去重和完整性校验 |
| metadata_json | TEXT | 供应商响应等非核心元数据 |
| created_at | TEXT | 时间 |

前端访问使用 `GET /api/assets/{id}`，由后端根据 `local_path` 返回文件。数据库不直接暴露服务器绝对路径。

### 5.8 `task_events`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增事件序号，便于 SSE 重放 |
| task_id | TEXT FK | 任务 |
| event_type | TEXT | `created/progress/status/result/error` |
| status | TEXT | 事件发生后的任务状态 |
| payload_json | TEXT | 事件详情 |
| created_at | TEXT | 时间 |

任务状态每次变化都写一条事件。SSE 断线后可用 `Last-Event-ID` 从该序号继续读取。

## 6. 异步任务执行

第一阶段使用进程内后台任务加 SQLite 锁，保持依赖最少。任务创建后立即落库，后台 worker 执行以下状态机：

```text
pending -> running -> succeeded
                   -> failed
                   -> canceled
                   -> unknown
```

异步供应商流程：

1. 读取任务和凭证，调用供应商创建接口。
2. 保存 `provider_task_id`，写入 `running` 事件。
3. 按退避间隔轮询状态，更新 `progress` 和 `task_events`。
4. 成功后下载结果 URL，校验 HTTP 状态、MIME 和文件大小。
5. 写入 `assets`，把资产 ID 写回任务。
6. 失败保存可读错误、`request_id` 和请求快照摘要，按 `retryable` 决定是否允许重试。

服务重启后的恢复：启动时扫描 `pending/running/unknown` 任务；对有 `provider_task_id` 的任务恢复轮询。使用 `submission_state` 和 `client_request_id` 记录提交边界；只有确定未发送的任务可以重新提交。请求已发出但任务 ID 未落库时，优先使用供应商幂等键或查询接口核对；无法核对则把任务标记为 `unknown` 并交由用户决定，避免重复生成与扣费。使用 `next_poll_at`、`deadline_at` 和 worker 租约字段恢复过期任务；事务提交任务状态及对应事件，网络请求在事务外执行。MVP 使用一个 worker，后续可替换为独立任务进程。

## 7. 素材存储方案

MVP 使用 `apps/api/data/assets/{yyyy}/{mm}/{task_id}/`，数据库只保存相对路径。上传素材先写临时文件，完成 MIME、大小和 checksum 校验后再移动到正式目录。远程 URL 结果默认下载转存；若供应商明确提供长期稳定地址，可保留 `remote_url` 作为回源信息，但前端优先访问本地资产。

文件名使用平台生成的 ID，不使用用户输入。删除任务不立即删除素材，避免历史消息失效；后续增加资产引用计数和清理策略。大文件和正式部署时，把 `AssetStorage` 接口替换为 S3、MinIO 或对象存储即可。

## 8. Agent 如何读取模型和偏好

每次 Agent turn 开始时，`ConversationService` 调用 `ModelCatalogService` 和 `PreferenceService`，生成结构化的运行时上下文：

```json
{
  "defaults": {"text": "codex", "image": "mock-image", "video": "mock-video"},
  "allowed_capabilities": ["text", "image_generation"],
  "agent_permissions": {"image": true, "video": false},
  "style": "简洁、专业",
  "settings": {"image": {"aspect_ratio": "1:1", "count": 1}}
}
```

Agent 的工具目录只暴露用户允许的工具，例如 `generate_image`、`generate_video`、`analyze_image`。工具参数由服务端再次校验，不能只依赖模型自行遵守。Agent 先判断意图：普通问答直接使用文本模型；用户明确要求图片且权限开启时调用图片工具；视频权限关闭时返回可解释提示；存在输入资产时把资产 ID 传给图生图或多模态工具。

工具执行结果写入 `generation_tasks` 和 `assets`，再以结构化结果回传 Agent，让 Agent 可以继续解释、引用或发起下一步任务。

## 9. API 草案

```text
GET    /api/providers
POST   /api/providers
PATCH  /api/providers/{provider_id}
PUT    /api/providers/{provider_id}/credentials
DELETE /api/providers/{provider_id}/credentials/{credential_id}
POST   /api/providers/{provider_id}/test-connection
POST   /api/providers/{provider_id}/refresh-models
GET    /api/models?capability=image_generation
POST   /api/providers/{provider_id}/models
PATCH  /api/models/{model_id}
POST   /api/preferences
GET    /api/preferences

POST   /api/generation-tasks
GET    /api/generation-tasks
GET    /api/generation-tasks/{task_id}
POST   /api/generation-tasks/{task_id}/cancel
POST   /api/generation-tasks/{task_id}/retry
GET    /api/generation-tasks/{task_id}/events

POST   /api/assets/upload
GET    /api/assets/{asset_id}
```

统一错误响应包含 `code`、`message`、`request_id` 和可选 `retryable`。所有创建接口支持客户端幂等 ID，避免网络重试重复生成。

## 10. 分阶段开发计划

### 第一阶段：本地 Codex 主线、模型配置和辅助 Mock

新增数据库迁移和 Repository：`model_providers`、`provider_credentials`、`models`、`user_preferences`、`generation_tasks`、`assets`、`task_events`。注册本地 Codex 为默认真实 Agent，沿用现有进程、会话和认证。增加模型目录、偏好、供应商配置与 API Key 加密管理页面。Mock 图片、视频仅在测试或开发模式显式启用，结果标识为模拟，不展示为真实供应商已接通。

验收：不配置第三方 Key，仍可连接本机 Codex 完成真实对话并从 SQLite 恢复历史；页面可保存与重启后读取密钥配置状态，接口和日志不泄露 Key；Mock 完成同步、异步、失败与重试的辅助验证。尚未实现适配器的供应商显示“待接入”，不能显示连接成功。第一阶段的模型配置用于建立目录、偏好和凭证闭环；若尚未实现某个模型的真实调用路由，切换该模型不能改变当前本地 Codex 的实际执行目标。

### 第二阶段：真实文本模型和 Agent 默认模型

在已保留的 Codex 接入基础上，实现一个明确协议的 OpenAI 兼容文本适配器。开源用户可以通过页面配置 Key、Base URL 和模型 ID 发起真实对话，服务端记录实际 provider/model。测试期间继续用本地 Codex 做真实 Agent 验证；未提供外部 Key 时，HTTP 适配器使用契约测试，并明确标注“未实测”，不冒充真实联调通过。完整第三方 Agent 编排作为独立后续能力。

验收：用户切换默认文本模型后新消息使用新模型，旧消息不受影响。

### 第三阶段：真实图片生成

选择一个供应商先接入文生图。实现凭证读取、同步或异步结果归一化、远程 URL 下载、本地资产服务和前端结果展示。

验收：提示词生成图片，图片在本地保存，任务和资产可从历史恢复。

### 第四阶段：真实视频生成

接入一个视频供应商，实现创建任务、轮询、进度事件、取消、重试、超时和视频转存。前端展示排队中、生成中、成功和失败状态。

验收：服务重启后未完成任务可以继续轮询，结果不会只依赖临时 URL。

### 第五阶段：多模态和资产编排

实现上传图片、图生图、图生视频和图片分析。允许 Agent 把前一步生成的资产作为下一步工具输入，增加资产引用和清理策略。再按实际 API 可用性接入火山引擎、阿里百炼、MiniMax 等适配器。

## 11. 本阶段实现边界与风险

第一阶段只保证网关契约、数据库结构、Mock 任务和前端配置闭环，不假设各供应商的具体 API 已稳定，也不把供应商模型名称硬编码在路由中。真实适配器需要逐家确认鉴权方式、区域、内容格式、异步状态枚举、结果有效期和计费规则。

主要风险是不同供应商的参数和输出差异很大，因此 Provider 适配器必须保留 `raw_metadata`，同时在平台层只暴露稳定的公共参数。异步任务不能只放在内存里，任务表和事件表必须先写入，再启动执行。前端的流式展示属于独立链路问题，登记为后续待办，修复时应同时验证 SSE 事件是否持续发送、浏览器是否逐事件读取、React 状态是否增量更新。

## 12. 检查清单

- [ ] 所有模型调用都能确定 provider、model、capability 和 task type
- [ ] API Key 可在页面录入并加密保存，也支持明确的环境变量来源
- [ ] 当前真实 Agent 测试继续使用本机 Codex，不以 Mock 替代
- [ ] 文本、图片、视频和多模态调用都统一创建 generation task
- [ ] `generation_tasks` 保存原始业务请求、规范化请求和脱敏供应商请求
- [ ] 远程素材尽量转存，本地资产有稳定访问接口
- [ ] 状态变化、错误和结果都写入 task_events
- [ ] Agent 工具受用户偏好和模型白名单约束
- [ ] 页面历史只读取 SQLite
- [ ] 现有 Codex 会话、reasoning 和 Markdown 能力保持兼容
- [ ] 前端流式过程展示待单独修复和验收
