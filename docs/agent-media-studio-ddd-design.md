# 造境 Agent 多模态与短剧工作台技术方案

版本：v1.0
日期：2026-11-21
适用范围：当前本地 FastAPI + Next.js + SQLite + 本地 Codex App Server 项目

## 1. 结论与总体取舍

建议把产品演进为两个前台工作台、一个共享创作内核：

1. **多模态创作工作台**：用户通过自然语言驱动 Codex Agent，生成和编辑图片、视频、音频，并管理候选结果、版本、任务和素材。
2. **短剧制作工作台**：从创意、故事设定、剧本、拆解、角色与场景资产、分镜关键帧、镜头视频、配音、字幕到整集合成，形成可追踪的制作流水线。

两者共用以下基础设施与领域能力：

- Agent 对话与工具调用；
- 模型/供应商路由；
- ComfyUI 工作流运行时；
- 统一生成任务；
- 素材与版本库；
- 项目、预算、审批、审计与事件流。

架构上采用**模块化单体 + 独立任务 Worker**，不建议第一阶段拆成微服务：

- 用户是本地单用户或小团队，当前 SQLite 和单机 GPU 已能满足早期需求；
- 多模态生成的主要复杂度是长任务、工作流适配、素材血缘和一致性，不是服务数量；
- 领域边界仍按 DDD 划分，通过端口、应用服务和领域事件隔离，后续可按热点单独拆服务。

核心原则：

- **Agent 不直接访问 ComfyUI**，也不直接操作 SQLite 或文件系统。Agent 只能调用受控的业务工具。
- **ComfyUI 节点图不直接暴露给 Agent**。节点图由可发布、可版本化的工作流模板管理，Agent 提供业务参数和素材引用。
- **生成任务与执行运行分离**。业务任务表达“要生成什么”，工作流运行表达“某次实际如何执行”。
- **所有生成结果都是不可变素材版本**。重新生成不覆盖旧文件，保留输入、工作流、模型和参数血缘。
- **短剧流水线由确定性状态机驱动，LLM 负责创作与判断**。不能依赖一个超长 Agent 循环隐式完成整集制作。
- **重要节点必须有人类审批**。剧本、拆解、资产方案、批量生成和最终合成都不应由 Agent 自行越过审批。

## 2. 当前实现基线与主要缺口

当前项目已经具备：

- Next.js 通过同源 `/api` 访问 FastAPI；
- FastAPI 以 JSON-RPC 连接本地 Codex App Server；
- 会话、回合、消息、推理过程和中断能力；
- SQLite 持久化；
- Provider、Model、Credential、GenerationTask、Asset、TaskEvent 的基础表；
- 火山方舟文本、图片和视频的基础适配；
- API Key 本地加密保存；
- 分层依赖和测试基础。

面向目标产品，主要缺口是：

| 缺口 | 影响 |
|---|---|
| 没有 ComfyUI Provider 和 Workflow 模板体系 | 无法稳定执行本地工作流，也无法管理版本和依赖 |
| 当前生成任务依赖进程内 `asyncio.create_task` | API 重启后任务丢失，不能可靠恢复 |
| 当前没有事务 Outbox、租约和重试策略 | 状态更新和事件通知可能不一致 |
| Codex 工具回调和业务用例尚未连接 | Agent 还只能聊天，不能真正驱动生成 |
| 素材模型缺少项目、校验和、版本、血缘和引用计数 | 难以支持候选比较、短剧一致性、清理和追溯 |
| 短剧没有独立领域模型 | 剧本、分镜、镜头和资产若都塞进会话消息，后续无法维护 |
| Provider 抽象仍偏火山 API | 外部模型与本地工作流难以统一路由 |
| 当前路径和模块按技术层组织 | 业务继续增长后会出现跨模块耦合 |

## 3. 目标与非目标

### 3.1 目标

- 本地 Codex 能通过受控工具生成图片、视频和音频。
- ComfyUI 可配置多个本地实例和多个版本化工作流。
- 同一套业务请求可以路由到 ComfyUI 或外部 API。
- 任务支持排队、执行、进度、取消、失败、重试、恢复和审计。
- 支持候选结果比较、素材引用、输入输出血缘和版本锁定。
- 支持短剧领域的分阶段制作与审批。
- 所有跨模块协作可以通过领域事件和幂等处理恢复。
- 本地部署不要求云数据库、消息队列或对象存储。

### 3.2 非目标

- 第一阶段不做通用可视化节点编辑器；只导入和配置经过验证的 ComfyUI 工作流。
- 第一阶段不让 Agent 任意安装节点、下载模型或访问任意 URL。
- 第一阶段不做多人实时协作、细粒度 RBAC 和云端多租户。
- 第一阶段不做专业 NLE 级视频剪辑；最终合成基于版本化时间线和 FFmpeg。
- 不把 ComfyUI 当成剧本数据库或业务状态机。

## 4. 限界上下文与上下文映射

```text
                         +-----------------------+
                         | Project / Workspace   |
                         | 项目、成员、预算、偏好 |
                         +-----------+-----------+
                                     |
             +-----------------------+------------------------+
             |                                                |
             v                                                v
  +----------------------+                       +------------------------+
  | Conversation / Agent |                       | Short Drama Production |
  | 会话、回合、工具调用   |                       | 剧本、拆解、分镜、审批   |
  +----------+-----------+                       +-----------+------------+
             |                                               |
             | 应用服务 / 工具端口                            | 制作编排
             +-----------------------+-----------------------+
                                     |
                                     v
                         +-----------------------+
                         | Media Generation      |
                         | 统一生成任务、候选、重试 |
                         +-----+-----------+-----+
                               |           |
                    +----------v--+    +---v------------------+
                    | Workflow    |    | Provider / Model     |
                    | Runtime     |    | Gateway              |
                    | 模板、执行、进度|    | ComfyUI、外部 API     |
                    +------+------+    +----------+-----------+
                           |                      |
                           +----------+-----------+
                                      |
                         +------------v------------+
                         | Asset Library           |
                         | 素材、版本、血缘、存储    |
                         +-------------------------+
```

### 4.1 上下文职责

| 上下文 | 类型 | 核心职责 | 主要聚合 |
|---|---|---|---|
| Project / Workspace | 通用支撑 | 项目、本地用户、偏好、预算、保留策略 | `Project` |
| Conversation / Agent | 核心 | 会话、Codex Thread、Turn、工具调用轨迹、流式事件 | `ConversationSession`、`Turn` |
| Media Generation | 核心 | 图片/视频/音频生成意图、任务状态、候选、重试、审批 | `GenerationTask` |
| Workflow Runtime | 核心支撑 | ComfyUI 工作流模板、编译、提交、进度、取消、恢复 | `WorkflowTemplate`、`WorkflowExecution` |
| Asset Library | 核心支撑 | 上传、生成结果、不可变版本、引用、校验、存储 | `Asset`、`AssetVersion` |
| Provider / Model Gateway | 核心支撑 | 供应商实例、模型目录、凭证、能力、健康检查、路由 | `ProviderConnection`、`ModelDefinition` |
| Short Drama Production | 核心 | 剧本、故事圣经、拆解、镜头、资产绑定、时间线、制作运行 | `DramaProject`、`ScriptVersion`、`ScenePlan`、`ProductionRun` |
| Production Orchestration | 应用编排 | 跨上下文 Saga、审批门、批量任务和最终合成 | `ProductionRun` 的流程状态 |
| Observability / Audit | 通用 | 追踪、事件日志、指标、脱敏审计 | `AuditRecord` |

### 4.2 上下文关系

- **Short Drama Production → Media Generation**：短剧只提交业务能力请求，不感知 ComfyUI 节点。
- **Media Generation → Workflow Runtime / Provider Gateway**：任务由路由策略选择本地工作流或外部模型。
- **Workflow Runtime / Provider Gateway → Asset Library**：执行结果统一登记为素材版本。
- **Conversation / Agent → 各业务应用服务**：通过工具端口调用，不能访问其他上下文 Repository。
- **Project / Workspace → 所有上下文**：提供项目 ID、归属、权限和预算边界。
- **Short Drama Production → Asset Library**：通过素材引用和版本 ID 关联，不复制二进制。

### 4.3 防腐层

对 ComfyUI、火山方舟、OpenAI 兼容平台等外部系统都必须有防腐层：

- 外部请求/响应只存在于 Infrastructure Adapter；
- 外部状态码、错误结构、任务 ID 转换为平台内部类型；
- 外部 URL、base64、文件名不能直接进入领域模型；
- Provider 特有参数保存在 `provider_options`，公共参数由领域契约定义；
- 领域层不依赖 Codex、ComfyUI、FastAPI、SQLite 或 httpx。

## 5. 领域模型设计

### 5.1 Project / Workspace

`Project` 是所有创作内容的边界：

- `id`、`owner_id`、`name`、`description`；
- `mode`：`general` 或 `short_drama`；
- `default_settings_json`：默认画幅、风格、语言、并发和审批策略；
- `budget_policy_json`：单任务、单集和每日上限；
- `status`：`active`、`archived`；
- `created_at`、`updated_at`。

关键不变量：

- 所有任务、会话、素材和短剧项目必须属于同一 Project；
- 跨项目素材引用默认禁止，除非用户显式复制为项目素材；
- 归档项目只读，但保留任务和素材血缘。

本地版本可固定 `owner_id=local-user`，但数据结构保留归属字段，避免未来改造全部主键关系。

### 5.2 Conversation / Agent

保留现有 `sessions`、`turns`、`messages` 的兼容性，但明确：

- `ConversationSession` 是产品会话，不等同于 Codex Thread；
- Codex Thread ID 只是外部执行上下文；
- 一次用户提交对应一个 `Turn`；
- Agent 发起的工具调用作为 Turn 下的 `ToolInvocation` 持久化；
- 消息可引用任务、素材和创作实体，但不复制任务状态。

`ToolInvocation` 至少记录：

- 工具名、调用 ID、参数摘要；
- 关联 Task / Asset / Script / Shot ID；
- 操作类型：read / draft / commit / expensive / destructive；
- 状态、人工确认记录、错误、耗时；
- 请求和响应的脱敏快照。

### 5.3 Media Generation

`GenerationTask` 是业务生成任务聚合根：

- `id`、`request_id`、`client_request_id`；
- `project_id`、`session_id`、`turn_id`；
- `purpose`：如 `workbench.asset`、`drama.keyframe`、`drama.shot_video`；
- `capability`：`image.generate`、`image.edit`、`video.generate`、`audio.tts` 等；
- `status`、`progress`、`priority`；
- `parent_task_id`：重试或变体来源；
- `pinned_context_json`：生成时锁定的剧本、故事圣经、镜头和参考素材版本；
- `original_request_json`、`normalized_request_json`；
- `routing_snapshot_json`：选中的 Provider、模型/工作流版本和参数；
- `result_asset_version_ids_json`；
- `deadline_at`、`retry_count`、`error_code`、`error_message`；
- 创建、更新、完成时间。

建议状态机：

```text
draft -> queued -> preparing -> submitted -> running
                                      |          |
                                      +----------+----> succeeded
                                                     -> failed
                                                     -> canceled
                                                     -> unknown
```

约束：

- `succeeded` 必须有至少一个已持久化的结果素材版本；
- 已完成任务的结果不允许原地改变，只能创建派生任务；
- 同一 `client_request_id` 只能创建一个任务；
- 重试创建新的 `GenerationAttempt`，任务本身保留统一历史；
- 外部请求可能已发出但没有收到任务 ID 时，必须进入 `unknown`，不能盲目重提。

### 5.4 Workflow Runtime

`WorkflowTemplate` 是可编辑的模板聚合根：

- 名称、能力、目标 Provider 实例；
- 草稿、当前发布版本、停用状态；
- 所属项目和可见范围。

`WorkflowVersion` 是发布后不可变的实体/快照：

- `template_id`、`version`、`graph_hash`；
- `api_graph_json`：ComfyUI API 格式节点图；
- `input_schema_json`：业务输入及类型约束；
- `bindings_json`：业务参数到节点 ID/字段的映射；
- `output_bindings_json`：结果从哪些节点和字段提取；
- `requirements_json`：自定义节点、模型文件、显存和建议参数；
- `capability_contract_version`；
- `published_at`、`published_by`。

`WorkflowExecution` 表示一次实际执行：

- `generation_task_id`、`workflow_version_id`、`provider_connection_id`；
- `provider_run_id`：ComfyUI `prompt_id`；
- `compiled_graph_json` 或独立快照文件引用；
- `submission_state`：`not_sent`、`submitting`、`accepted`、`unknown`；
- 状态、进度、当前节点、错误、节点执行时间；
- 租约、心跳、轮询时间和截止时间。

关键不变量：

- 已发布版本不可修改；编辑必须产生新版本；
- 任务必须固定 WorkflowVersion，不使用“当前最新版本”执行；
- API 图哈希和编译后参数必须可复现；
- Agent 不能提交未发布模板。

### 5.5 Asset Library

`Asset` 是逻辑素材，`AssetVersion` 是不可变文件版本：

- Asset：项目、名称、媒体类型、来源、用途、标签、当前版本；
- AssetVersion：文件、MIME、大小、宽高、时长、checksum、存储键、来源任务；
- `AssetLink`：输入素材、参考图、首帧、末帧、配音、字幕、成片等语义关系；
- `AssetReview`：候选评分、选中、弃用原因。

文件路径建议：

```text
data/assets/{project_id}/{asset_id}/{version_id}/{safe_filename}
```

数据库只保存相对存储键，不保存绝对路径。文件写入顺序：

1. 写入临时文件；
2. 校验大小和 MIME；
3. 计算 SHA-256；
4. 使用原子重命名进入正式目录；
5. 事务写入 AssetVersion；
6. 发布 `AssetVersionCreated` 事件。

删除采用“归档 + 引用检查 + 延迟清理”，不随任务删除立即删文件。

### 5.6 Short Drama Production

短剧领域建议拆为以下聚合，避免一个巨型 `DramaProject` 聚合导致更新冲突。

#### DramaProject

- 标题、类型、受众、语言、画幅、目标集数；
- 当前故事圣经版本、当前剧本版本；
- 项目状态：`draft`、`development`、`in_production`、`completed`、`archived`；
- 默认制作配置和审批策略。

#### StoryBibleVersion

- 角色、地点、道具、时代、视觉风格、色彩、镜头语言；
- 角色外观、声音、性格和连续性约束；
- 每个版本不可变；
- 角色和地点可拥有参考素材包 `ReferencePack`。

#### ScriptVersion

- 集、场、角色、对白、动作、旁白、情绪和节奏；
- 原始文本和结构化 JSON 同时保存；
- `draft -> in_review -> approved -> superseded`；
- 审核通过后不可变，后续修改建立新版本。

#### ScenePlan

- 场景级拆解聚合根；
- 包含有序 `Shot` 实体；
- 每个 Shot 至少包含：景别、机位、动作、对白、时长、情绪、参考角色/地点/道具、首帧提示词、视频提示词、音频需求和连续性约束；
- 场景拆解可并行编辑，减少整集聚合锁竞争。

#### ShotAssetBinding

- Shot 与 AssetVersion 的语义绑定；
- 类型：`character_ref`、`location_ref`、`first_frame`、`last_frame`、`clip`、`voice`、`subtitle`；
- 选定版本和候选状态；
- 绑定后覆盖需重新审批并增加版本。

#### TimelineVersion

- 集级剪辑时间线；
- 镜头顺序、入点、出点、转场、字幕、音频轨；
- 固化所引用的每个素材版本；
- 可导出为 FFmpeg 合成清单。

#### ProductionRun

- 一次“生成整集/整场/整批镜头”的编排状态；
- 固定剧本版本、故事圣经版本、ScenePlan 版本和默认工作流版本；
- 记录阶段、已完成镜头、失败镜头、成本和审批；
- 通过 Saga 协调跨上下文任务，不直接持有所有任务聚合。

## 6. 代码组织结构

建议从当前技术层结构逐步迁移为“上下文优先，上下文内再分层”：

```text
apps/api/app/
├── shared/
│   ├── domain/
│   │   ├── ids.py
│   │   ├── events.py
│   │   ├── errors.py
│   │   └── types.py
│   ├── ports/
│   │   ├── clock.py
│   │   ├── unit_of_work.py
│   │   ├── event_publisher.py
│   │   └── asset_storage.py
│   └── infrastructure/
├── contexts/
│   ├── projects/
│   ├── conversations/
│   ├── media_generation/
│   ├── workflow_runtime/
│   ├── assets/
│   ├── providers/
│   └── drama/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── interfaces/
├── agent/
│   ├── tool_registry.py
│   ├── tool_executor.py
│   └── context_builder.py
├── api/
│   └── routes/
├── worker/
│   ├── scheduler.py
│   ├── generation_worker.py
│   ├── outbox_worker.py
│   └── production_saga_worker.py
├── composition.py
└── main.py
```

每个上下文内部遵循：

```text
domain/
  entities.py
  value_objects.py
  aggregates.py
  events.py
  policies.py
  ports.py
application/
  use_cases.py
  handlers.py
infrastructure/
  repositories.py
  adapters.py
interfaces/
  schemas.py
  routers.py
```

依赖规则：

- `domain` 不依赖 FastAPI、Pydantic HTTP Schema、SQLite、httpx；
- `application` 只依赖 domain、ports 和 shared；
- `infrastructure` 实现 domain/application 端口；
- `interfaces` 负责 HTTP/MCP/SSE 转换；
- 跨上下文只能调用目标上下文的公开应用端口，不能直接导入其 Repository；
- `composition.py` 是唯一装配具体实现的位置；
- 增加 `import-linter` 或自定义测试，禁止上下文间私有导入和领域层反向依赖。

迁移策略：

1. 保留现有 `/api/conversations`、`/api/providers`、`/api/generations` 兼容路由。
2. 先把现有 `GenerationService` 拆为 Media Generation 用例、Workflow Runtime 和 Provider Adapter。
3. 把 `ConversationRepository` 中的生成任务方法迁移到对应上下文 Repository。
4. 原模块保留薄适配层，前端无需一次性重写。

## 7. 核心业务流程

### 7.1 ComfyUI 接入与工作流发布

```text
管理员导入 API 格式工作流
  -> 服务端读取节点图并与 /object_info 校验
  -> 标记业务输入、节点字段绑定和输出提取规则
  -> 检查自定义节点、模型文件、显存和参数约束
  -> 使用示例参数执行烟雾测试
  -> 保存草稿版本
  -> 人工确认后发布为不可变 WorkflowVersion
```

需要明确区分：

- ComfyUI 前端保存的 UI Workflow JSON；
- ComfyUI 的 API Prompt JSON；
- 平台内部的工作流清单。

平台只执行 API 格式节点图。UI JSON 需要先在 ComfyUI 中导出/转换为 API 格式，并由服务端做结构校验。不要依赖 Agent 自动“猜”节点字段。

### 7.2 Agent 驱动一次图片生成

```text
用户：给主角生成 4 张雨夜街头的角色定妆照
  -> Codex 读取项目上下文与可用工具
  -> 调用 project.get_context / asset.search
  -> 调用 media.submit_generation
  -> AgentToolBridge 校验参数、权限、预算和幂等 ID
  -> MediaGeneration 创建 GenerationTask + Outbox 事件
  -> Worker 领取任务
  -> CapabilityRouter 选中 ComfyUI 模板版本
  -> WorkflowCompiler 绑定提示词、参考图和参数
  -> ComfyUIClient 提交 /prompt，保存 prompt_id
  -> Worker 接收进度并更新 task_events
  -> 下载输出、校验、登记 AssetVersion
  -> 发布 TaskSucceeded
  -> SSE 与工具结果返回 Agent/UI
  -> Agent 展示候选并邀请用户选择
```

Agent 的回复不得早于任务和素材持久化。工具结果至少返回：

```json
{
  "taskId": "task-...",
  "status": "succeeded",
  "assetVersionIds": ["..."],
  "previewUrls": ["/api/assets/.../content"],
  "elapsedMs": 18320,
  "providerRunId": "prompt-..."
}
```

二进制不进入 LLM 上下文。图片可返回受控缩略图 URL；视频返回封面图和素材引用。

### 7.3 外部模型与 ComfyUI 统一路由

```text
GenerationTask
  -> 读取显式 target；若没有，则读取项目默认路由
  -> 校验 capability、输入类型、输出类型、预算、健康状态
  -> 选择:
       workflow_template -> Workflow Runtime
       direct_model      -> Provider Gateway Adapter
  -> 两种执行统一映射为 GenerationAttempt
  -> 两种结果统一登记为 AssetVersion
```

路由优先级：

1. 用户对当前任务显式选择的 Provider/模型/模板；
2. 当前 Shot 或项目配置的默认路由；
3. 项目按能力配置的默认路由；
4. 系统默认路由。

自动降级只允许发生在用户配置了降级策略、能力完全兼容且成本未超预算的情况下。不能因为 ComfyUI 不可用就静默切到收费外部模型。

### 7.4 短剧从创意到成片

| 阶段 | 主要输入 | 主要输出 | 执行方式 | 审批门 |
|---|---|---|---|---|
| 创意与大綱 | 用户 Brief | 故事概念、分集大纲 | Codex 创作 | 用户确认方向 |
| 故事圣经 | 大纲 | 角色、地点、道具、风格、连续性规则 | Codex + 人工编辑 | 版本锁定 |
| 剧本 | 故事圣经、大纲 | ScriptVersion | Codex 生成、人工改写 | 剧本审核通过 |
| 拆解 | 已审批剧本 | ScenePlan、Shot 列表、时长预算 | Codex 结构化输出 + 规则校验 | 拆解审核通过 |
| 资产计划 | 剧本、ScenePlan、故事圣经 | 角色/地点参考包、Shot 绑定计划 | Codex + Asset Library | 资产方案确认 |
| 参考资产 | 资产计划 | 角色定妆、场景概念、道具图 | ComfyUI/外部图片模型 | 选中并锁定版本 |
| 分镜关键帧 | Shot、参考资产 | 首帧/关键帧候选 | Image-to-Image/参考图工作流 | 逐镜或批量审核 |
| 镜头视频 | 已选关键帧、镜头提示词 | Shot Clip 候选 | Image-to-Video 工作流 | 逐镜或批量审核 |
| 声音 | 对白、角色声音 | TTS、音效、环境声 | TTS/外部音频模型 | 音频审核 |
| 合成 | 已通过镜头、声音、字幕 | TimelineVersion、整集成片 | FFmpeg | 成片审核 |

推荐的首版短剧流水线先用“AI 拆解 + 规则校验 + 人工审批”保证结构可靠，再逐步提高自动化率。

## 8. ComfyUI 工作流运行时详细设计

### 8.1 Provider Connection

ComfyUI 以 `ProviderConnection` 注册，而不是伪装成普通模型：

- `id`、`project_id`；
- `adapter_key=comfyui`；
- `base_url`，默认仅允许本机地址或显式白名单地址；
- `client_id`；
- 认证方式：无认证、反向代理 Header 或受控 Token；
- 最大并发数，单消费级显卡通常为 1；
- 默认超时、轮询间隔和租约时间；
- `enabled`、最近健康检查结果。

API 后端访问 ComfyUI，浏览器不直接访问 `127.0.0.1:8188`。

### 8.2 工作流清单契约

示意：

```json
{
  "templateKey": "local-sdxl-character-sheet",
  "version": 3,
  "capability": "image.generate",
  "executionAdapter": "comfyui",
  "apiGraph": {},
  "inputs": [
    {
      "key": "prompt",
      "type": "string",
      "required": true,
      "maxLength": 4000,
      "bind": {"nodeId": "6", "field": "text"}
    },
    {
      "key": "seed",
      "type": "integer",
      "minimum": 0,
      "maximum": 2147483647,
      "bind": {"nodeId": "3", "field": "seed"}
    },
    {
      "key": "referenceImage",
      "type": "asset",
      "mimeTypes": ["image/png", "image/jpeg"],
      "bind": {"nodeId": "12", "field": "image"}
    }
  ],
  "outputs": [
    {
      "nodeId": "9",
      "field": "images",
      "assetType": "image"
    }
  ],
  "requirements": {
    "customNodes": ["example-node-pack"],
    "models": ["model-name-in-comfyui"],
    "minVramGb": 12
  }
}
```

绑定层负责：

- 类型检查；
- 枚举、范围、长度和 MIME 限制；
- 素材上传和本地文件名替换；
- 输出节点精确定位；
- 禁止 Agent 写入未声明字段。

### 8.3 执行步骤

1. Worker 通过数据库租约领取 `queued` 任务。
2. 校验 WorkflowVersion、ProviderConnection、能力和预算。
3. 拉取输入 AssetVersion，确认文件存在且校验和一致。
4. 调用 ComfyUI 上传接口登记输入素材，得到 ComfyUI 内部文件名。
5. 编译器复制固定 API 图，注入业务参数和输入引用，产生编译图快照。
6. 在提交前记录 `submission_state=submitting`。
7. 调用 `/prompt` 提交，保存 `prompt_id`，更新 `submission_state=accepted`。
8. 优先通过 WebSocket 获取执行、进度和错误事件；WebSocket 不可用时轮询 queue/history。
9. 根据 `output_bindings` 精确提取结果，不递归扫描任意 URL。
10. 通过受控 `/view` 下载输出到临时文件。
11. 使用文件签名和媒体解析器校验 MIME、尺寸、时长和完整性。
12. 登记不可变 AssetVersion，并原子更新任务结果和领域事件。

### 8.4 提交、重试与恢复

ComfyUI 的提交接口通常不能提供与平台相同的业务幂等键，因此必须保存提交边界：

- 网络失败且确定请求未离开 Worker：可以重试；
- 已发送但未收到 `prompt_id`：标记 `unknown`，先查询 ComfyUI 队列和历史；
- 无法确认：交由用户决定，不自动重复提交；
- 已获取 `prompt_id`：服务重启后按 ID 恢复查询，不重新提交；
- 每次重试创建新的 WorkflowExecution，旧的保留审计记录；
- Worker 使用 `lease_owner`、`lease_expires_at` 和心跳，防止重复执行；
- 取消时区分排队任务和运行任务：排队任务从队列移除，运行任务发送中断请求；
- 后台定时扫描过期租约、长时间无进度的执行和僵尸任务。

### 8.5 并发与 GPU 资源

- 每个 ComfyUI 实例配置容量，默认 `maxConcurrency=1`；
- 调度器按 Provider 容量发放执行权限；
- 视频、批量镜头和单图任务应有不同优先级和队列配额；
- 同一 ProductionRun 的批量任务可分阶段并行，但不能突破本地 GPU 容量；
- 对队列长度、预计等待时间、任务截止时间进行限制和前端提示；
- 不以无限创建 `asyncio.Task` 实现并发。

### 8.6 自定义节点与模型文件

- 自定义节点由部署者安装和升级，Agent 无安装权限；
- 模板发布时记录依赖节点类型和模型文件；
- 通过 `/object_info` 检查节点是否存在，通过受控实例能力信息尽量检查模型；
- 未知节点、未声明模型和超出显存要求时拒绝发布或执行；
- 工作流模板与 ComfyUI 版本应有兼容范围；
- 外部导入工作流视为不可信输入，服务端必须校验结构、节点数量和参数边界。

### 8.7 安全边界

- ComfyUI 只监听本机或受控网络；
- 所有远程 URL 下载经过 SSRF 防护和域名/IP 策略；
- 禁止用户直接指定任意服务器文件路径；
- 上传和输出文件使用平台生成 ID；
- 输出下载大小、时长和压缩比有限制；
- 清理 prompt、Authorization、Cookie 和签名 URL 日志；
- 对 ComfyUI 返回的错误做归一化，不直接暴露内部路径。

## 9. Agent 架构

### 9.1 Agent 与业务的连接方式

建议定义 `AgentToolBridge`，它只做四件事：

1. 将 Codex 工具调用映射到应用用例；
2. 校验当前项目、会话、操作权限和人工确认；
3. 将结果转换为安全、紧凑的工具响应；
4. 记录 ToolInvocation 和追踪信息。

实现上可以优先使用本地 Codex App Server 的 Dynamic Tool 能力；如果当前固定版本对动态工具注册支持不稳定，则实现同契约的本地 MCP Server 作为适配器。两种方式共用同一套应用用例，不让领域层感知接入协议。

当前项目已固定 Codex App Server schema，其中包含 `item/tool/call` 服务端请求和动态工具响应类型。接实现时必须按 vendor 中的固定 schema 联调注册字段、参数结构和错误格式，不能只依赖记忆中的协议。

### 9.2 工具目录

初始工具集：

| 工具 | 作用 | 风险级别 | 默认审批 |
|---|---|---|---|
| `project.get_context` | 获取项目摘要、版本、预算和能力 | read | 自动 |
| `asset.search` | 搜索素材和版本 | read | 自动 |
| `media.submit_generation` | 提交图片/视频/音频任务 | expensive | 超过阈值需确认 |
| `media.get_task` | 查询任务和结果 | read | 自动 |
| `media.cancel_task` | 取消任务 | commit | 自动，受归属校验 |
| `drama.save_script_draft` | 保存剧本草稿 | draft | 自动 |
| `drama.submit_script` | 提交剧本审核 | commit | 必须确认 |
| `drama.plan_breakdown` | 生成拆解提案 | draft | 自动 |
| `drama.save_breakdown_draft` | 保存拆解草稿 | draft | 自动 |
| `drama.submit_breakdown` | 提交拆解审批 | commit | 必须确认 |
| `drama.bind_asset` | 将素材版本绑定到镜头 | commit | 必须确认 |
| `production.create_run` | 创建批量制作运行 | expensive | 必须确认和预算检查 |
| `production.assemble_episode` | 合成成片 | commit | 必须确认 |

不提供：

- 任意 SQL；
- 任意 shell；
- 任意文件读写；
- 直接 ComfyUI `/prompt`；
- 直接修改 Provider 凭证；
- Agent 自审批；
- 无限批量生成。

### 9.3 Agent 角色拆分

“多 Agent”首先是职责和提示词契约的拆分，不必一开始做独立进程：

- **Creative Director**：面向用户，理解意图，协调工具；
- **Script Writer**：生成和修改结构化剧本；
- **Breakdown Planner**：把剧本拆成 Scene/Shot；
- **Asset Planner**：识别所需角色、地点、道具和参考图；
- **Prompt Director**：按工作流能力生成结构化媒体提示词；
- **Continuity Reviewer**：检查角色、服装、场景、光线和叙事连续性。

每个角色都有版本化输入/输出 JSON Schema。编排器调用它们，但状态机和审批门由普通代码控制。

### 9.4 上下文构建

不要向 Agent 注入整部剧本和全部历史。`ContextBuilder` 按任务组装：

- 项目摘要和制作偏好；
- 当前剧本/故事圣经版本摘要；
- 当前 Scene 和少量相邻 Shot；
- 相关角色/地点/道具的规范描述；
- 已锁定素材缩略图和版本 ID；
- 可用能力、工作流模板、预算和审批策略；
- 上一步工具结果和未解决问题。

原始长文本保存在数据库，通过摘要、检索和显式工具读取按需加载。

### 9.5 审批与预算

工具调用分为四种策略：

- `auto`：只读或低成本草稿；
- `confirm`：写入已批准版本、改变制作状态；
- `budgeted`：按预计时长、GPU 占用或外部金额判断是否确认；
- `forbidden`：凭证、系统配置、自定义节点安装和任意文件访问。

用户确认需要生成一次性 `confirmation_token`，绑定工具、参数摘要、项目、过期时间和调用者。Agent 不能用自然语言声称“用户已同意”绕过。

## 10. Provider / Model Gateway 扩展设计

### 10.1 统一执行端口

```python
class MediaExecutionPort(Protocol):
    async def health(self) -> ProviderHealth: ...

    async def submit(self, request: CompiledMediaRequest) -> ExecutionHandle: ...

    async def inspect(self, handle: ExecutionHandle) -> ExecutionStatus: ...

    async def cancel(self, handle: ExecutionHandle) -> None: ...

    async def collect(self, handle: ExecutionHandle) -> list[ArtifactTransfer]: ...
```

- ComfyUI 实现：将工作流模板编译为 API Graph；
- 火山方舟/其他直接 API：将 Canonical Request 转换为厂商请求；
- 外部异步视频 API：`submit` 返回 Provider Task ID，`inspect` 轮询；
- 外部同步图片 API：`submit` 可直接返回已就绪结果，但任务持久化与素材登记流程保持一致。

### 10.2 能力契约

能力不能只靠模型名称判断，应由模型目录或工作流模板显式声明：

- `image.generate`
- `image.edit`
- `image.understand`
- `video.generate`
- `video.image_to_video`
- `audio.tts`
- `audio.generate`
- `media.analyze`
- `workflow.execute`

每个能力声明：

- 输入媒体类型和数量；
- 输出媒体类型；
- 支持比例、尺寸、时长和参数 schema；
- 同步/异步；
- 预估成本和资源需求；
- 是否支持取消、种子复现和批次输出；
- 当前状态：`planned`、`testing`、`ready`、`disabled`。

### 10.3 外部模型接入步骤

1. 定义 Adapter 和能力映射；
2. 建立厂商请求/响应 Fixture 和契约测试；
3. 配置凭证、Base URL、区域和接入点；
4. 执行连接测试和最小真实调用；
5. 把任务状态映射到平台状态机；
6. 把结果 URL/base64 转为 ArtifactTransfer；
7. 记录脱敏请求快照和错误；
8. 只有真实联调通过后标记 `ready`。

## 11. 数据与持久化方案

### 11.1 本地 MVP 数据库

继续使用 SQLite 作为本地版本事实来源，但需要：

- 开启 WAL；
- 设置 busy timeout；
- 单写者 Worker 或有限写并发；
- 所有长时间网络请求在数据库事务外执行；
- 每条事件带自增序号，支持 SSE `Last-Event-ID` 重放；
- 使用正式迁移文件，不再只依赖启动时增量补列。

当出现云部署、多人并发或高吞吐 Worker 时，迁移到 PostgreSQL。领域模型、应用服务和 API 契约不变，只替换 Repository 与 UnitOfWork。

### 11.2 建议的表

| 上下文 | 表 |
|---|---|
| Project | `projects`、`project_settings` |
| Conversation | 现有 `sessions`、`turns`、`messages`，新增 `tool_invocations` |
| Providers | 现有 `model_providers`、`provider_credentials`、`models`，增加连接能力和健康字段 |
| Workflow | `workflow_templates`、`workflow_versions`、`workflow_executions` |
| Media | 增强 `generation_tasks`，新增 `generation_attempts` |
| Assets | 重构为 `assets`、`asset_versions`、`asset_links`、`asset_reviews` |
| Drama | `drama_projects`、`story_bible_versions`、`script_versions`、`scene_plans`、`shots`、`shot_asset_bindings`、`timeline_versions`、`timeline_items`、`production_runs` |
| 基础设施 | `task_events`、`outbox_events`、`inbox_events`、`idempotency_keys` |

### 11.3 兼容迁移

当前 `generation_tasks` 和 `assets` 可以渐进迁移：

1. 为现有任务补 `project_id`、`purpose`、`pinned_context_json`；
2. 创建默认本地项目并回填旧数据；
3. 将每个旧 Asset 转换为 Asset + 初始 AssetVersion；
4. 保留旧列读取兼容，新写入逐步切换到新模型；
5. 完成数据校验后再删除兼容逻辑。

### 11.4 事务 Outbox

以下操作在同一数据库事务中完成：

- 创建 GenerationTask；
- 写入初始 TaskEvent；
- 写入 OutboxEvent；
- 写入幂等键。

Worker 轮询 Outbox，把事件分发给：

- SSE/前端；
- Short Drama Saga；
- 工具结果；
- 审计和指标。

消费者使用 `event_id` 去重。即使重复投递，处理结果必须一致。

## 12. API 设计

### 12.1 项目与 Agent

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}

GET    /api/projects/{project_id}/conversations
POST   /api/projects/{project_id}/conversations
POST   /api/conversations/{conversation_id}/messages
POST   /api/conversations/{conversation_id}/interrupt
GET    /api/conversations/{conversation_id}/messages
GET    /api/conversations/{conversation_id}/events
```

### 12.2 生成任务与素材

```text
POST   /api/projects/{project_id}/generation-tasks
GET    /api/projects/{project_id}/generation-tasks
GET    /api/generation-tasks/{task_id}
POST   /api/generation-tasks/{task_id}/cancel
POST   /api/generation-tasks/{task_id}/retry
GET    /api/generation-tasks/{task_id}/events

POST   /api/projects/{project_id}/assets/upload
GET    /api/assets/{asset_id}
GET    /api/assets/{asset_id}/versions
GET    /api/asset-versions/{version_id}/content
POST   /api/asset-versions/{version_id}/review
```

### 12.3 Provider 与 Workflow

```text
GET    /api/providers
POST   /api/providers
PATCH  /api/providers/{provider_id}
POST   /api/providers/{provider_id}/test-connection
GET    /api/models?capability=video.generate

GET    /api/workflow-templates
POST   /api/workflow-templates/import
POST   /api/workflow-templates/{template_id}/validate
POST   /api/workflow-templates/{template_id}/publish
GET    /api/workflow-versions/{version_id}
```

### 12.4 短剧

```text
GET    /api/projects/{project_id}/drama
PATCH  /api/projects/{project_id}/drama

POST   /api/drama-projects/{drama_id}/outline
POST   /api/drama-projects/{drama_id}/scripts
GET    /api/drama-projects/{drama_id}/scripts
POST   /api/script-versions/{version_id}/submit-review
POST   /api/script-versions/{version_id}/approve

POST   /api/script-versions/{version_id}/breakdown
GET    /api/production-plans/{plan_id}/scenes
PATCH  /api/scenes/{scene_id}
POST   /api/production-plans/{plan_id}/submit-review
POST   /api/production-plans/{plan_id}/approve

POST   /api/scenes/{scene_id}/asset-plan
POST   /api/shots/{shot_id}/bind-asset
POST   /api/production-runs
GET    /api/production-runs/{run_id}
POST   /api/production-runs/{run_id}/cancel

POST   /api/episodes/{episode_id}/timelines
POST   /api/timelines/{timeline_id}/render
GET    /api/timelines/{timeline_id}
```

### 12.5 统一生成请求

```json
{
  "clientRequestId": "client-01J...",
  "projectId": "project-...",
  "sessionId": "session-...",
  "purpose": "drama.keyframe",
  "capability": "image.generate",
  "prompt": "雨夜街头，电影感侧光，角色穿深色风衣",
  "negativePrompt": "文字, 水印, 畸形手指",
  "inputAssetVersionIds": ["asset-version-..."],
  "parameters": {
    "width": 1024,
    "height": 1536,
    "count": 4,
    "seed": null
  },
  "routing": {
    "mode": "workflow",
    "providerConnectionId": "local-comfy",
    "workflowVersionId": "workflow-version-..."
  },
  "pinnedContext": {
    "scriptVersionId": "script-...",
    "shotId": "shot-..."
  },
  "approvedBudget": null
}
```

### 12.6 SSE 事件

事件名建议：

- `task.created`
- `task.queued`
- `task.submitted`
- `task.progress`
- `task.asset_ready`
- `task.succeeded`
- `task.failed`
- `task.canceled`
- `tool.started`
- `tool.completed`
- `production.stage_changed`

示例：

```json
{
  "eventId": 1842,
  "type": "task.progress",
  "taskId": "task-...",
  "status": "running",
  "progress": 63,
  "message": "视频采样中",
  "providerRunId": "prompt-...",
  "traceId": "trace-..."
}
```

前端断线重连时携带 `Last-Event-ID`，服务端从事件表继续发送。任务状态事实来源始终是数据库，SSE 只负责通知。

## 13. 前端工作台设计

### 13.1 多模态创作工作台

建议布局：

- 左侧：项目、会话、任务历史、素材库；
- 中间：Agent 对话与创作画布/结果网格；
- 右侧：当前结果详情、参数、来源、生成版本和操作；
- 底部或浮动任务坞：排队、进度、失败、取消、重试。

关键交互：

- Agent 对话中的工具卡片可展开查看任务进度和结果；
- 图片/视频结果可直接作为下一次生成输入；
- 支持候选并排比较、锁定、弃用和创建变体；
- 重新生成必须显示使用的提示词、参考素材和工作流版本；
- 刷新页面后从数据库恢复全部任务和结果。

### 13.2 短剧工作台

建议分为四个主视图：

1. **剧本工作室**：大綱、故事圣经、剧本编辑器、版本对比和审批；
2. **拆解台**：场次表、镜头列表、时长预算、连续性和缺失资产提示；
3. **镜头画板**：每个镜头的参考图、首帧、视频候选、审核状态；
4. **成片时间线**：镜头顺序、音频、字幕、转场和导出。

每一步展示确定的版本号、审批人和下游影响。上游变更时提示需要失效或重新生成的镜头，而不是静默重做。

### 13.3 前端状态策略

- REST 获取持久化快照；
- SSE 接收增量事件；
- 收到事件后更新任务局部状态，并以节流方式刷新关联查询；
- 工具调用、任务和消息各自有独立状态机；
- 不使用前端内存作为任务事实来源；
- 大列表使用分页和虚拟滚动，媒体 URL 使用缩略图；
- 对视频结果提供封面帧、总时长和按需播放。

## 14. 可靠性、可观测性与安全

### 14.1 可靠性与恢复

- 所有长任务先落库再执行；
- Outbox 保证业务状态和事件一致；
- Worker 租约与心跳避免重复领取；
- 启动时恢复可确认的 ComfyUI 执行；
- 不可确认的提交进入 `unknown`；
- 任务事件单调追加，不覆盖历史；
- 失败错误分为可重试、不可重试和需要人工处理；
- 对外部模型和 ComfyUI 设置超时、截止时间和最大重试次数；
- 数据迁移可重复执行，并在启动前检查一致性。

### 14.2 可观测性

所有链路共享 `trace_id`：

- 用户消息；
- Agent Turn；
- ToolInvocation；
- GenerationTask；
- Worker Attempt；
- WorkflowExecution / Provider Task；
- AssetVersion；
- ProductionRun。

关键指标：

- 各 Provider 队列长度、等待时间、执行时长；
- 成功、失败、取消、unknown 比例；
- ComfyUI 节点耗时和失败节点；
- 任务重试率；
- 素材生成字节数和存储增长；
- 短剧各阶段通过率和重做率；
- 每集预计/实际 GPU 时间和外部费用；
- Agent 工具调用成功率、审批拒绝率。

日志只记录脱敏后的请求摘要、图哈希、Provider Task ID 和错误码。不记录凭证、原始 base64、完整签名 URL。

### 14.3 安全

- Provider 凭证继续使用成熟认证加密库保存；
- API Key 不进入 Codex 上下文和工具参数；
- Agent 工具只能使用当前项目资源；
- 路径必须解析后校验在允许目录内；
- 上传文件限制大小、数量、MIME 和扩展名；
- 远程结果下载防止 SSRF 和无限重定向；
- ComfyUI 管理接口不暴露到公网；
- 自定义节点安装与模型下载只由部署者执行；
- 重要操作写审计记录；
- 对批量生成、成本、删除和导出设置显式权限与确认。

## 15. 测试策略

### 15.1 领域测试

- 任务状态不能非法回退；
- 成功任务必须有资产；
- 已发布工作流不可修改；
- 已审批 ScriptVersion 不可原地变更；
- Shot 变更导致下游绑定失效规则；
- 项目和素材引用边界；
- 重试与 unknown 状态规则；
- Saga 重复事件处理幂等。

### 15.2 契约测试

- ComfyUI Adapter 固定成功、节点错误、队列满、超时、断线、取消和输出缺失 Fixture；
- 外部 Provider 固定请求/响应 Fixture；
- WorkflowCompiler 金丝雀快照；
- OutputBinding 精确提取测试；
- SSE 重放和工具响应 Schema 测试。

### 15.3 集成与端到端测试

- 测试 ComfyUI 实例执行一个轻量固定工作流；
- Fake Codex Agent 调用工具，创建任务、完成素材并返回；
- 服务重启后恢复已提交任务；
- 短剧从 ScriptVersion 到 ScenePlan 的结构化流程；
- 多镜头批量任务中部分失败、重试和最终合成；
- 浏览器刷新后恢复任务与候选；
- 真实 GPU 烟雾测试与 CI 契约测试分开，不能把 Mock 结果宣传为真实模型成功。

## 16. 分阶段实施计划

### 阶段 0：领域基础与事务可靠性

交付：

- 引入上下文目录和依赖规则；
- 增加 Project 归属；
- 增加 Outbox、幂等键和任务租约；
- 将当前进程内生成任务改为数据库 Worker；
- 增加 AssetVersion 基础模型和迁移；
- 保留旧 API 兼容层。

验收：

- 服务重启后任务状态和消息历史不丢失；
- 同一客户端请求不会创建重复任务；
- 任务状态和事件在同一事务中产生；
- 现有对话、流式回复和测试不回归。

### 阶段 1：Codex + ComfyUI 最小闭环

交付：

- ComfyUI Provider Connection；
- 工作流导入、输入绑定、输出绑定、校验和发布；
- 一个文生图模板和一个图生视频模板；
- Agent Dynamic Tool/MCP 工具桥；
- 任务进度、取消、失败、结果下载和素材展示。

验收：

- 用户在对话中要求生成图片，Codex 调用工具，本地 ComfyUI 实际执行；
- 图片保存为 AssetVersion，刷新后仍可访问；
- 执行中可看到任务进度，可取消；
- API 重启后可恢复已获得 `prompt_id` 的任务；
- Codex 无法直接读取路径、凭证或调用任意 ComfyUI 节点。

### 阶段 2：多模态创作工作台

交付：

- 项目、素材库、任务坞；
- 候选结果比较、材质版本、锁定和派生；
- 图生图、参考图、图生视频；
- 外部图片/视频 Provider 接入一个真实供应商；
- 预算、超时和路由提示。

验收：

- 不同来源结果都进入统一任务和资产模型；
- 用户可看到每个结果的来源和生成参数；
- ComfyUI 不可用时不会静默切换到收费模型；
- 可把一个生成结果作为下一次任务输入。

### 阶段 3：短剧前期创作与拆解

交付：

- DramaProject、StoryBibleVersion、ScriptVersion；
- 结构化剧本和人工编辑；
- ScriptVersion 审批；
- ScenePlan/Shot 拆解；
- 版本对比、规则校验和拆解审批；
- 资产计划与角色/地点参考包。

验收：

- 已审批剧本不可原地修改；
- 每个 Shot 能追溯到 ScriptVersion 和 ScenePlan；
- 角色、地点、道具缺失时有明确提示；
- 拆解 JSON 错误不会进入后续生成。

### 阶段 4：短剧批量制作

交付：

- ProductionRun 和 Saga；
- Shot 关键帧、参考图、视频、TTS 和字幕；
- 逐镜审核、批量重试和部分失败恢复；
- TimelineVersion 与 FFmpeg 合成；
- 一集成片导出。

验收：

- 单镜头失败不阻塞其他已完成镜头；
- 所有成片镜头引用固定素材版本；
- 上游剧本或故事圣经变更能识别需要重做的内容；
- 生成整集前明确展示预算和预计等待；
- 最终成片可从数据库重建制作清单。

### 阶段 5：扩展与产品化

交付：

- 第二个外部视频模型或多个 ComfyUI 实例；
- Provider 健康、配额和成本策略；
- 更强的连续性和角色一致性检查；
- 备份、迁移、素材清理和导出；
- 可选 PostgreSQL、对象存储和独立 Worker 部署。

## 17. 关键风险与决策

| 风险 | 应对 |
|---|---|
| ComfyUI 工作流格式和节点版本漂移 | WorkflowVersion + 依赖清单 + 发布校验 + 固定图哈希 |
| 单卡 GPU 排队时间过长 | Provider 容量、优先级、批次限制、预计等待和取消 |
| 提交成功但响应丢失导致重复扣时/重复生成 | submission_state、幂等、历史核对、unknown 人工确认 |
| Agent 生成错误结构化剧本 | JSON Schema、规则校验、人工审批、低成本草稿先审 |
| 短剧角色和场景不一致 | 故事圣经版本、参考素材包、固定版本绑定、连续性审查 |
| 批量制作成本失控 | 预算策略、审批门、每阶段预估、逐镜可取消 |
| 外部模型协议差异大 | Canonical Request + Adapter + 契约测试 + 能力显式声明 |
| 大文件与 SQLite 混合存储风险 | 文件系统/对象存储保存二进制，数据库只存元数据和相对键 |
| 一个巨型短剧聚合造成并发冲突 | 按 ScenePlan、ScriptVersion、TimelineVersion 拆聚合 |
| Agent 获得过大权限 | 工具白名单、项目边界、确认 Token、禁止 shell/任意 SQL/任意 URL |

建议形成以下架构决策记录：

1. ADR-001：模块化单体优先，不提前拆微服务；
2. ADR-002：ComfyUI 通过工作流模板和 Provider Adapter 接入；
3. ADR-003：生成任务、工作流执行和素材版本分离；
4. ADR-004：短剧以版本化领域模型和审批状态机为基础；
5. ADR-005：Agent 只能通过受控工具修改业务状态；
6. ADR-006：SQLite 支持本地版本，云端多租户时迁移 PostgreSQL。

## 18. 第一版实施的推荐纵向切片

为了最快验证架构，不要先做完整的短剧 UI。第一版按以下纵向切片推进：

```text
一个本地项目
  -> 一个 Codex 会话
  -> Agent 调用 media.submit_generation
  -> 一个已发布 ComfyUI 文生图工作流
  -> 一个持久化 GenerationTask
  -> 一个独立 Worker
  -> 一个 AssetVersion
  -> SSE 任务进度
  -> 对话结果卡片和素材详情
```

该切片验收通过后，再增加图生视频和短剧领域。只要这个切片中的端口、状态机、幂等、任务恢复和素材血缘正确，后续增加模型和短剧阶段都是扩展，而不是重写。

## 19. 短剧制作控制面（当前实现）

短剧上下文已经从单一文档/镜头编辑器扩展为“创作对象 + 专业角色 + 质量门”：

```text
drama/
  domain.py       项目、分集计划、资产槽位、镜头槽位、角色手册、审核记录
  application.py  分集规划、镜头规划、角色审核、用户放行、连续性审计
  repository.py   SQLite 持久化与重启恢复
  routes.py       制作控制室、审核、分集计划、资产与镜头槽位 API
```

### 19.1 专业角色

角色定义是领域中的版本化静态契约，不是散落在 Prompt 里的说明文字。当前包含：

| ID | 角色 | 主要阶段 |
|---|---|---|
| `screenwriter` | 编剧 | Brief、故事圣经、剧本 |
| `director` | 导演 | 圣经、剧本、拆解、关键帧、镜头、时间线 |
| `production_designer` | 场景师 / 美术指导 | 圣经、资产、关键帧 |
| `costume_makeup` | 定妆 / 服装师 | 圣经、资产、关键帧 |
| `lighting` | 灯光师 | 资产、关键帧、镜头 |
| `continuity_supervisor` | 场记 / 连续性监督 | 拆解、资产、关键帧、镜头、时间线 |
| `first_assistant_director` | 执行导演 | 拆解、资产、关键帧、镜头、时间线 |
| `editor` | 剪辑 / 声音 | 镜头、时间线 |

每个角色声明 `responsibilities`、`required_inputs`、`deliverables`、
`checklist` 和 `review_criteria`。Agent 在起草前必须先读取角色手册。

### 19.2 审核门语义

`drama_reviews` 保存每次角色审核和用户决定：

- `agent` 只能记录待审、通过、要求修改或失败；
- Agent 的“通过”只表示专业检查完成，不表示项目阶段已批准；
- `reviewer=user` 的 `stage_gate` 记录才允许阶段进入下一阶段；
- 当前门状态由最新角色审核和最新用户决定计算；
- 自动审核发现问题时，Agent 可以生成新草稿并重新检查，但不得静默批准。

### 19.3 结构化分集与专业资产槽位

分集计划持久化以下字段：

- 时间范围；
- 地点；
- 内景/外景；
- 人物；
- 场次；
- 故事节拍；
- 画面要求；
- 对白要求；
- 连续性风险。

角色实体使用 `asset_slots_json` 保存可复用槽位。人物以单张 16:9
`character_sheet` 为专业定妆资产，同一张图内包含头部与面部特写、全身正面/侧面/
背面、表情特写以及服装与材质细节；场景包括总场景、内景、外景和灯光参考。镜头的
`grid9_asset_id` 与 `storyboard_asset_id` 与首帧、尾帧、视频、音频并列，
确保九宫格和故事板不是一次性聊天附件。

角色实体的 `profile_json` 保存人物创作档案，分集 `plan_json.sceneContracts` 保存
逐场目标、障碍、战术、转折、潜台词、表演和视听策略。它们让编剧自审、导演拆镜、
表演设计、资产提示词和视频提示词共享同一叙事事实源。

短剧交互采用审查优先模型：Agent 读取已确认的创意框架后，负责专业草稿、确定性
审核、角色自审和修订；用户主要批准、否决、要求重做或确认成本/内容边界。专业字段
可以保留人工覆盖能力，但不应成为默认必经表单。

### 19.4 Agent 工具

新增受控短剧工具：

- `zaojing_get_drama_roles`
- `zaojing_get_drama_control_room`
- `zaojing_get_drama_episode`
- `zaojing_audit_drama_episode`
- `zaojing_audit_drama_script`
- `zaojing_save_drama_draft`
- `zaojing_plan_drama_episodes`
- `zaojing_plan_drama_shots`
- `zaojing_plan_drama_assets`
- `zaojing_bind_drama_asset`
- `zaojing_review_drama_stage`

镜头规划工具只允许写入尚无场次的分集，避免覆盖用户在 UI 中修改的拆解。
媒体绑定工具负责把生成结果写回实体或镜头的业务语义槽位；实体图片槽位只接受
图片，镜头视频和音频槽位分别校验素材类型。资产页可以按槽位调用兼容图片工作流，
关键帧页可以分别生成首帧、尾帧、九宫格连续帧和电影故事板。失败任务可以从持久化
规范请求重试，异步视频任务在 API 重启后按供应商任务 ID 恢复轮询。工具运行时版本
提升为 `12`，旧会话会在下一次消息时重建 Codex Thread。

### 19.5 后续迭代

短剧前端的全局层采用“三段主流程 + 关系画布 + 精细编辑”：

- 顶栏只显示剧本、制作资产库、分镜三个主阶段；
- 当前主阶段的子步骤显示在内容区顶部；
- 制作画布用剧本、分集拆解、资产、镜头、后期五条关系链展示项目全貌；
- 画布节点携带预览、完成状态和数量，点击进入对应精细编辑器；
- 画布支持拖动平移、缩放与复位，分组和节点可自由移动并保存项目级布局；
- 剧本、分集、资产、镜头和输出的 SVG 关系曲线根据实际节点几何实时重算；
- 节点先打开属性检查器再进入编辑器，镜头节点可直接带上下文进入关键帧或视频阶段；
- 工作区明确分为全局、分集、阶段三种范围。全局显示跨阶段关系，分集显示逐集拆解
  与该集产物链，阶段显示 Agent 任务、产物清单、负责角色和审核门；
- 阶段产物状态由真实文档、逐集计划、资产槽位、镜头槽位、音频、字幕和导出记录计算，
  Agent 请求会携带当前范围的明确缺口；
- 工作台主体固定为“中间实时结果 + 右侧 Agent 对话”，每个项目/分集/阶段映射到独立
  会话线程 key，避免 20 集项目的对话和结果相互污染；
- conversation/session 表持久化 project_id、episode_id 和 scope，本地浏览器映射只
  用于快速恢复当前标签页，历史语义仍以数据库为准；
- Agent 的写操作工具完成后发出工作区刷新信号，中间结果会重新加载文档、分集、资产、
  镜头、任务和审核门；
- 每条嵌入对话消息会以隐藏传输上下文携带项目、分集和阶段 ID；重新加载历史时剥除
  上下文前缀，保持用户可见转录干净；
- 分集审计会在 ProductionRun 创建、启动和失败项重试时再次执行。计划字段、场次/镜头
  描述或引用存在阻断错误时，批量生成不会进入队列；审计警告保留给用户和 Agent 判断，
  不会静默升级为拒绝；
- 对白说话人会忽略“画外”“V.O.”等括号表演提示进行角色匹配，但数据库中的原始
  剧本文本保持不变；
- 画布提供浅色/深色主题，默认浅色无限画布、半透明分组、白色节点卡和细关系线；
- 选中节点使用画布内浮动属性卡，右侧固定保留 Agent 对话，不把编辑和对话混在同一栏；
- 剧本阶段采用阅读优先的独立文档工作区，按故事设定、分集大纲和剧本正文组织，
  显示集数、预计时长、字数和审批状态，并把下一步收口到拆解阶段；
- 短剧采用固定的四区布局：产品导航、制作范围导航、实时工作区和 Agent 对话；
  项目态不再显示营销标题，宽屏业务页使用全部剩余空间，画布首屏自动适应内容；
- 多参考视频任务会把已绑定的九宫格连续帧和故事板纳入参考素材与提示词，按动作顺序、
  景别、机位和视觉焦点保持连续性；
- 右侧 Agent 是工作区内的真实布局列，不使用抽屉、浮层或遮挡式展开；宽屏与画布并排，
  窄屏依次排列，避免覆盖实时制作结果。

该结构参考即梦的短剧流程与 RunningHub 的关系画布，但业务事实来源仍是本地
SQLite 中的 DramaProject、分集、镜头、资产、审核门和任务记录，不把画布位置当作
业务状态。

1. 把角色审核清单做成可配置版本，支持不同题材和平台的审核模板。
2. 已增加阶段修订号、旧审核失效和用户审批失效传播；分集/镜头差异对比仍待实现。
3. [已完成] 增加资产候选比较与锁定血缘，避免主素材被静默覆盖。
4. [已完成] 增加制作运行编排：批量关键帧、九宫格、故事板和镜头视频的任务图。
5. 已接入部分失败、任务 ID 固定、失败项重试和 API 重启恢复；阶段内容变化会使旧审批失效。预算与等待策略继续迭代。
6. 将 ComfyUI 工作流扩展冻结，按需一次性人工比对和重新导入。
