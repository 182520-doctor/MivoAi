# 造境通用创作 Agent 工作流设计（v2）

版本：v2.0（待确认稿）  
日期：2026-09-13  
状态：已完成项目工作空间接入与自动执行基础闭环，结构化阶段执行持续开发中  
首个落地领域：纯文本剧本创作  

## 1. 设计目标

> 当前实现说明：创作项目创建后，前端可以自动启动一次 Agent Turn；该 Turn
> 使用项目工作空间和项目专属 Codex Thread，完成后将阶段文件变化同步到
> SQLite 产物版本和工作流状态。阶段级 Schema 校验、连续性检查和人工审批
> 仍属于后续迭代。

造境不能只做一个“输入一句话、模型返回一大段文本”的聊天页面。它需要成为一个可以持续工作的创作工程系统：用户提出一个模糊创意，Agent 经过多轮沟通，把创意逐步发展为可检查、可修改、可继续生产的项目成果。

本设计首先支持以下场景：

- 单个 3 分钟短片剧本。
- 单个 10 分钟短片剧本。
- 10 集、每集 3 分钟的连续短剧。
- 更长篇幅的系列故事。
- 用户中途修改角色、结局、风格或某一集后，系统可以分析影响并保持前后连续。
- 用户关闭页面、重启服务或过几天回来后，可以从上次进度继续。

后续在同一内核上扩展：

- 小说、广告文案、故事策划等纯文本创作。
- 分镜设计、角色设定图、场景图和道具图。
- 文生图、图生图、文生视频、图生视频。
- 多集短剧生产、配音、音乐、剪辑和成片管理。

核心结论：

```text
创作 Agent = 通用创作工程内核 + 领域包 + 项目数据 + 执行模型

通用创作工程内核
  = 项目 + 工作空间 + 工作流 + 节点 + 产物 + 版本 + 质量门禁

剧本领域包
  = 剧本 Schema + 剧本 Skill + 故事知识库 + 连续性检查器 + 剧本工作流模板

执行模型
  = Codex App Server + Codex Thread + 多轮 Turn
```

## 2. 最重要的设计原则

### 2.1 业务项目、工作空间和 Codex Thread 分离

三者有关联，但不是一回事：

| 概念 | 负责什么 | 是否是事实源 |
|---|---|---|
| 创作项目 Project | 用户正在制作的作品及其业务状态 | 是 |
| 工作空间 Workspace | 项目文件、结构化产物和可读文档所在目录 | 是，作为数据库之外的可移植副本 |
| Codex Thread | Agent 与模型的连续协作上下文 | 否，不能作为唯一项目记忆 |

示例：“一只猫的十集短剧”是一个项目；`runtime/projects/prj_cat_series/` 是这个项目的工作空间；`thr_xxx` 是当前导演 Agent 使用的 Codex Thread。

项目可以继续存在，即使 Thread 损坏、被压缩或更换模型。项目也可以拥有多个 Thread，例如一个主导演 Thread、一个连续性审查 Thread 和一个备选结局分支 Thread。

### 2.2 不能依赖聊天记录维持长期连续性

聊天历史会越来越长，模型上下文会压缩，也可能遗漏早期细节。因此“主角怕水”“第二集丢失了红色项圈”“第五集才知道医生身份”这类事实不能只藏在对话里。

长期连续性必须由以下内容共同保证：

- 数据库中的结构化项目状态。
- 工作空间中的故事圣经和阶段产物。
- 每次 Turn 开始前由 Context Builder 装配的相关上下文。
- 生成后的 Schema 校验、连续性校验和质量评审。

### 2.3 机器数据与人类文档双轨存储

只使用 Markdown 容易阅读，但难以可靠查询、关联和自动检查；只使用 JSON 便于机器处理，但用户难以审阅和修改。

因此采用双轨制：

```text
Canonical JSON / Database  -> 机器事实源，可校验、查询和关联
Rendered Markdown          -> 人类视图，可阅读、评审和导出
```

例如 `episode-03.json` 是第三集的结构化事实，`episode-03.md` 是根据同一版本渲染的阅读稿。正式修改必须形成新版本并同步更新两种表示，不能让两者各自漂移。

### 2.4 Skill、知识库和项目事实严格分工

| 类型 | 回答的问题 | 例子 |
|---|---|---|
| Skill | 应该怎样做 | 如何设计悬念、怎样拆分三分钟剧本 |
| 知识库 | 有哪些可参考的方法和资料 | 类型片结构、对白节奏、镜头语法资料 |
| 项目事实 | 这个作品已经确定了什么 | 角色、世界观、每集事件、道具状态 |
| 工作流 | 先做什么、后做什么、何时验收 | 先故事圣经，再季纲，再分集，再场景 |

Skill 不是项目记忆，知识库也不能替代故事圣经。用户确认过的项目事实优先级最高。

### 2.5 先形成提案，再提交正式版本

Agent 的生成结果不应直接覆盖已确认剧本。每次重要修改都遵循：

```text
生成草案 -> 结构校验 -> 连续性检查 -> 用户确认/自动门禁 -> 发布新版本
```

这样用户说“第三集不对”时，只产生第三集的新候选版本，并先给出对第四至十集的影响分析。

## 3. 总体架构

```text
前端创作台
  |- 项目导航
  |- Agent 对话
  |- 工作流进度
  |- 结构化大纲/剧本编辑器
  |- 产物与版本
  |- 连续性问题和质量报告
  |
  | REST：项目、节点、产物、版本、知识库
  | WebSocket：Turn 增量、公开进度、任务状态、用户介入
  v
FastAPI 应用层
  |- ProjectService          项目生命周期
  |- WorkflowEngine          工作流状态机
  |- AgentOrchestrator       Agent 执行编排
  |- ContextBuilder          本轮上下文装配
  |- ArtifactService         产物和版本管理
  |- ContinuityService       故事连续性检查
  |- KnowledgeService        知识检索、候选知识入库
  |- SkillRegistry           Skill 发现、版本和启用策略
  |- QualityGateService      Schema 和质量门禁
  |
  v
通用执行层
  |- Codex App Server Adapter
  |- Model Gateway（后续文本/图像/视频供应商）
  |- Background Worker（长任务、轮询、素材生成）
  |
  +--> SQLite / 后续 PostgreSQL
  +--> Project Workspace
  +--> Asset Storage
  +--> Knowledge Index
```

## 4. 通用创作领域模型

### 4.1 Project：业务聚合根

Project 表示一个用户可识别的创作任务，例如“一只猫的十集短剧”。它保存：

- 项目名称、类型、状态和所有者。
- 使用的工作流模板及版本。
- 当前阶段和整体进度。
- 工作空间路径。
- 默认 Agent、模型和偏好。
- 当前正式产物版本。
- 创建、归档和更新时间。

Project 不保存全部具体剧本文本；它负责把各类数据组织到同一业务边界中。

### 4.2 Workflow Definition：可复用流程模板

工作流定义描述一个创作类型“应该经过哪些阶段”。定义需要版本化，项目创建后固定使用某一版本，避免系统升级后老项目流程突然变化。

通用节点字段：

- `node_key`：稳定标识，如 `story_bible`。
- `name`：界面名称。
- `depends_on`：前置节点。
- `input_artifact_types`：需要读取的产物。
- `output_artifact_types`：必须生成的产物。
- `skill_refs`：执行时需要的 Skill 及版本。
- `knowledge_scopes`：允许检索的知识范围。
- `output_schema_ref`：结构化输出 Schema。
- `validators`：规则检查器和质量评审器。
- `approval_mode`：自动通过、必须用户确认或按风险决定。
- `retry_policy`：失败重试策略。

示意定义：

```yaml
id: screenplay-series
version: 1.0.0
domain: screenplay
nodes:
  - key: creative_brief
    outputs: [creative_brief]
    approval: user
  - key: story_bible
    depends_on: [creative_brief]
    skills: [story-architect@1]
    outputs: [story_bible]
    approval: user
  - key: series_outline
    depends_on: [story_bible]
    outputs: [series_outline, episode_outlines]
  - key: episode_screenplays
    depends_on: [series_outline]
    foreach: episode
    outputs: [episode_screenplay]
  - key: continuity_review
    depends_on: [episode_screenplays]
    outputs: [quality_report]
```

### 4.3 Workflow Run 和 Step Run：一次实际执行

Workflow Definition 是模板；Workflow Run 是某个项目的一次执行实例；Step Run 是其中一个节点的一次执行。

同一节点可执行多次，例如第三集剧本先后产生 v1、v2、v3。每次执行都记录输入版本、Skill 版本、模型、Thread、Turn、状态、输出版本和错误，保证结果可追溯。

### 4.4 Content Node：通用层级节点

为了让 3 分钟短片和十集短剧使用同一内核，引入通用内容树：

```text
Project
  -> Series / Standalone Work
    -> Season（可选）
      -> Episode
        -> Sequence（可选）
          -> Scene
            -> Shot（进入分镜和视频阶段后启用）
```

每个节点拥有稳定 ID、父节点、顺序、目标时长、状态和当前产物版本。不同领域可以注册新节点类型，例如小说的 `chapter`，广告的 `campaign/ad_variant`，音乐视频的 `music_section`。

三分钟单集并不是特例，它仍然是一个包含一个 Episode 的 Project；十集短剧则包含十个 Episode。这样工作流和接口不需要写两套。

### 4.5 Artifact：阶段产物

Artifact 表示一种可版本化成果，而不是某次聊天消息。例如：

- `creative_brief`
- `story_bible`
- `character_profile`
- `series_outline`
- `episode_outline`
- `scene_plan`
- `screenplay`
- `shot_list`
- `image_prompt_pack`
- `generated_image`
- `video_clip`
- `quality_report`

Artifact 只表示逻辑身份；Artifact Version 保存具体内容。每个版本记录：

- 结构化 JSON 内容。
- Markdown 或其他渲染文件路径。
- 来源 Step Run、Codex Thread、Turn 和模型。
- 父版本及变更说明。
- `draft/review/approved/superseded` 状态。
- Schema 版本和内容校验和。

### 4.6 Story Entity 和 Continuity Fact

剧本领域中的角色、地点、道具、事件和规则必须具有稳定 ID：

```text
char_cat_mimi       角色：咪咪
loc_old_station     地点：旧车站
prop_red_collar     道具：红色项圈
event_ep02_lost     事件：第二集项圈丢失
rule_cat_fears_water 规则：咪咪怕水
```

场景引用 ID，而不是只写“咪咪”和“项圈”两个字符串。连续性事实需要带时间范围和来源：

- 事实内容。
- 从哪一集、哪一场开始生效。
- 在哪一场失效或被改变。
- 来源产物版本。
- 是否已由用户确认。

这使系统能够检查“已丢失的项圈为什么在第三集无解释地出现”“角色尚未知道的秘密为什么提前说出”等问题。

## 5. 剧本领域统一 Schema

### 5.1 项目规格

```json
{
  "format": "short_series",
  "episode_count": 10,
  "target_duration_sec_per_episode": 180,
  "language": "zh-CN",
  "genre": ["喜剧", "成长"],
  "audience": "家庭观众",
  "tone": ["温暖", "轻松"],
  "platform": "竖屏短视频",
  "aspect_ratio": "9:16",
  "content_rating": "general"
}
```

时长必须是数据字段，不写死在 Skill 中。3 分钟、10 分钟或 10 集只是规格参数变化，工作流根据规模选择执行粒度。

### 5.2 故事圣经 Story Bible

故事圣经是全项目连续性的核心，至少包含：

- 一句话故事和核心命题。
- 类型、风格、目标受众和内容边界。
- 世界规则、时代、地点和时间逻辑。
- 主要角色档案、欲望、缺陷、秘密、关系和成长弧线。
- 关键地点和道具。
- 全季主线、支线和必须回收的伏笔。
- 禁止改变的硬约束。
- 可调整但需要记录的软约束。

### 5.3 系列大纲和分集大纲

系列大纲负责全局节奏，分集大纲负责每集承上启下。每集至少包含：

- 集号、标题、目标时长。
- 本集目标和核心冲突。
- 开场钩子、主要升级、转折、高潮和结尾钩子。
- 角色状态进入值和离开值。
- 新增事实、改变事实和待回收伏笔。
- 与上一集和下一集的连接。
- 场景列表和预计时长预算。

### 5.4 场景 Schema

每个 Scene 至少包含：

- `scene_id` 和所属 Episode。
- 场次号、内景/外景、地点、日/夜。
- 目标时长和叙事目的。
- 出场角色 ID、道具 ID、地点 ID。
- 进入状态、冲突、行动、转折和离开状态。
- 对白、动作和必要的表演提示。
- 前置事实和本场产生的新事实。
- 后续要回收的信息。

### 5.5 时长控制

模型不能仅凭“看起来像三分钟”判断时长。系统同时使用：

- 每集总时长预算。
- 各场景时长之和。
- 对白字数、动作密度和停顿的估算规则。
- 不同内容类型的容差。
- 用户最终校准值。

第一版建议允许目标时长上下 10% 的误差。后续通过真实成片数据校准中文对白速度、动作镜头长度和不同风格的节奏参数。

## 6. 十集三分钟短剧的完整执行示例

用户输入：

> 我有一只猫，给我写一个十集的短剧，每集三分钟。

### 6.1 意图识别与最少提问

系统识别到用户已经给出主角类型、集数和时长，但缺少类型、受众和主要矛盾。Agent 最多询问三个高价值问题：

1. 希望偏喜剧、冒险、治愈还是悬疑？
2. 猫生活在现实世界还是拟人世界？
3. 最希望观众记住什么情感或主题？

用户可以回答，也可以选择“由导演决定”。没有必要一次问完所有细节。

### 6.2 形成项目规格与创意提案

Agent 先生成 2 至 3 个差异明显的方向，只在创意方向上让用户做决定。用户选择后发布 `creative_brief v1`，系统再进入故事圣经阶段。

### 6.3 创建故事圣经

生成角色、世界、主线、支线、伏笔和结局边界。通过 Schema 校验和基本矛盾检查后，由用户确认。确认后的关键事实成为受保护的 Canon。

### 6.4 创建全季结构

先写十集的整体功能，而不是直接逐集写全文：

```text
第 1 集：建立目标，出现核心问题
第 2 集：第一次主动尝试并失败
第 3 集：获得伙伴，同时付出代价
...
第 9 集：最低谷与真相揭示
第 10 集：最终选择、主线解决、主题落点
```

系统检查十集是否存在重复功能、角色弧线断裂、伏笔无回收和高潮提前耗尽。

### 6.5 分集展开

每一集依次经历：

```text
分集大纲 -> 场景计划 -> 完整剧本 -> 本集连续性报告 -> 用户确认
```

不要求一次 Turn 生成十集完整剧本。建议每次处理一集或一个批次，完成后生成 `episode_summary` 和新的项目状态快照，供下一集读取。

### 6.6 用户中途修改

用户说：“第三集不要让猫找到项圈，改成第七集才找到。”

系统先建立 Change Request：

- 原事实：第三集找回项圈。
- 新事实：第七集找回项圈。
- 受影响范围：第 3 至第 7 集、相关角色动机、第四集某场对白、第六集伏笔。
- 建议修改方案和风险。

用户确认后，系统创建受影响产物的新版本；未受影响的第一、二、八至十集不会无意义重写。必要时使用 `thread/fork` 探索备选剧情，确定后再发布到主项目。

## 7. 通用工作流状态机

所有创作领域共享以下高层状态：

```text
INTAKE       理解需求
DISCOVERY    补充必要信息
DESIGN       形成结构和规则
PRODUCTION   生成具体内容
REVIEW       校验和评审
REVISION     修改受影响内容
APPROVAL     用户确认关键节点
PUBLISHED    发布正式版本
BLOCKED      缺少必要输入或外部任务失败
```

节点状态：

```text
pending -> ready -> running -> validating -> review_required
        -> approved -> completed
        -> failed / canceled / superseded
```

工作流引擎负责允许哪些状态转换，Agent 不能靠自然语言自行宣布“已完成”。只有所需产物存在、Schema 有效且质量门禁通过后，节点才能完成。

## 8. Agent 每一轮如何工作

每个用户请求进入以下统一管线：

1. **识别意图**：新建、继续、修改、提问、审批、撤销或创建分支。
2. **解析范围**：确定项目、工作流节点和内容节点，例如“第三集第 4 场”。
3. **建立执行记录**：创建 Workflow Step Run，冻结本轮输入版本。
4. **装配上下文**：读取项目摘要、相关 Canon、目标节点、依赖产物、用户偏好、Skill 和检索知识。
5. **调用 Codex**：在项目 `cwd` 下恢复或创建 Thread，并发起 Turn。
6. **流式展示**：前端展示公开计划、阶段进度、可读 reasoning summary 和正文增量。
7. **接收结构化结果**：按当前节点的 `outputSchema` 解析结果。
8. **验证**：Schema、引用完整性、时长、连续性和质量评审。
9. **保存候选版本**：数据库落库，工作空间生成 JSON 和 Markdown。
10. **提交或待审**：自动通过低风险产物；关键方向、Canon 和大范围修改等待用户确认。
11. **更新项目快照**：更新当前阶段、摘要、连续性事实和下一步建议。

用户在 Agent 正在执行时追加限制，可使用 `turn/steer`；Turn 已完成后的修改必须开启新 Turn，并形成新的 Change Request 或产物版本。

## 9. Context Builder：让 Agent 每次都看对内容

### 9.1 上下文优先级

每个 Turn 不读取整个工作空间，而按优先级组装：

1. 系统安全规则和当前工作流节点契约。
2. 用户本轮明确要求。
3. 已确认的项目硬约束和 Canon。
4. 当前节点及直接依赖产物。
5. 相邻内容摘要，例如当前集前后两集。
6. 检索到的相关角色、道具、地点和伏笔事实。
7. 当前节点需要的 Skill。
8. 与任务相关的知识库片段。
9. 更远历史的压缩摘要。

### 9.2 上下文包清单

每次执行保存 `context_manifest.json`，记录：

- 引用了哪些产物及版本。
- 引用了哪些实体和连续性事实。
- 使用了哪些 Skill 及版本。
- 检索了哪些知识文档和片段。
- 采用了哪个模型和推理强度。
- 哪些内容因预算被摘要或省略。

当结果出错时，可以追溯“模型当时究竟看到了什么”。

### 9.3 大项目的摘要策略

十集项目至少维护三层摘要：

- 项目级：主题、主线、结局、硬约束。
- 分集级：本集发生了什么、角色状态如何变化。
- 场景级：场景输入状态、事件和输出状态。

摘要不是替代原文，而是用于上下文路由。涉及具体修改时仍读取目标产物原文。

## 10. Codex App Server 映射方案

### 10.1 Thread 策略

推荐映射：

- 每个 Project 创建一个主导演 Thread。
- 关键评审可创建独立审查 Thread，避免把批评上下文污染主创作方向。
- 大型系列可以按工作流阶段创建辅助 Thread，但必须登记在 `project_threads`。
- 备选故事线使用 `thread/fork`，记录父 Thread 和分叉 Turn。
- Thread 是执行资源，不是项目数据库。

### 10.2 工作目录与权限

创建或恢复 Thread 时，把 `cwd` 指向项目工作空间，并限制写入根目录：

```text
cwd = runtime/projects/{project_id}
sandbox = workspaceWrite
writableRoots = [runtime/projects/{project_id}]
networkAccess = false（默认）
```

需要知识检索或外部资料时，由平台提供受控工具或临时开启明确范围，不让剧本 Agent 默认访问整个用户目录。

### 10.3 Turn 与结构化输出

- `turn/start`：每次独立的创作、修改、评审或问答。
- `outputSchema`：约束当前节点的机器输出，仅对当前 Turn 生效。
- `turn/steer`：用户在当前生成尚未完成时追加方向。
- `turn/interrupt`：用户停止生成。
- `turn/completed`：只表示模型轮次结束，不等于业务节点通过。
- `item/agentMessage/delta`：正文流式输出。
- `item/reasoning/summaryTextDelta` 和 `turn/plan/updated`：前端公开工作过程。

业务完成条件由 Workflow Engine 判断，不能直接使用 `turn/completed` 代替。

### 10.4 Skill 调用

服务端先按项目 `cwd` 调用 `skills/list`，得到实际可用 Skill。执行节点时同时传入文本标记和显式 Skill 输入项：

```json
[
  {"type": "text", "text": "$story-architect 为十集短剧建立全季故事结构"},
  {"type": "skill", "name": "story-architect", "path": "/.../SKILL.md"}
]
```

不能只在 Prompt 中声称“你拥有某 Skill”；必须记录实际解析到的路径和版本。Skill 变化事件触发缓存失效，老项目默认继续使用已固定版本，升级需要显式迁移。

## 11. Workspace 统一规范

```text
runtime/projects/{project_id}/
├── AGENTS.md                         项目级操作规则，自动生成
├── project.json                      项目清单、工作流版本和当前状态
├── state/
│   ├── current.json                  当前状态快照
│   ├── context-manifests/            每轮上下文清单
│   └── change-requests/              变更及影响分析
├── canon/
│   ├── story-bible.json
│   ├── story-bible.md
│   ├── entities.json
│   ├── continuity-facts.json
│   └── glossary.md
├── structure/
│   ├── series-outline.json
│   ├── series-outline.md
│   └── episodes/
│       └── ep-001/
│           ├── outline.json
│           ├── outline.md
│           ├── scenes.json
│           ├── screenplay.json
│           ├── screenplay.md
│           └── quality-report.json
├── production/                       后续多模态阶段启用
│   ├── shots/
│   ├── prompts/
│   ├── images/
│   ├── audio/
│   └── videos/
├── references/                       用户提供的项目参考资料
├── exports/                          导出的剧本、PDF、项目包
└── .zaojing/
    ├── workflow-lock.json            固定工作流版本
    ├── skill-lock.json               固定 Skill 版本
    └── artifact-index.json           文件与数据库 ID 对照
```

约束：

- 文件名使用稳定 ID 或固定编号，标题改变不导致路径变化。
- JSON 必须带 `schema_version`、`artifact_id` 和 `version`。
- Markdown 顶部带只读元数据，标明来源 JSON 版本。
- 所有正式产物通过 ArtifactService 写入，Agent 不直接修改数据库。
- `AGENTS.md` 只保存项目操作规则和文件索引，不塞入全部剧本内容。
- 数据库是应用查询和事务事实源；工作空间是可移植、可审阅和可恢复的项目包。两者通过版本号和校验和检查一致性。

## 12. Skill 体系设计

### 12.1 三层 Skill

```text
平台级 Skills
  |- artifact-editor       产物修改协议
  |- continuity-reviewer   连续性检查方法
  |- quality-reviewer      质量评审协议

领域级 Skills
  |- story-architect       故事架构
  |- character-designer    角色设计
  |- episode-planner       分集设计
  |- screenplay-writer     场景与对白写作
  |- script-doctor         剧本诊断
  |- shot-planner          分镜设计（后续）

项目级 Skills
  |- project-tone-guide    本项目专属风格规则
  |- franchise-rules       系列 IP 的特殊限制
```

### 12.2 Skill 内容规范

每个 Skill 至少定义：

- 名称、用途、适用阶段和不适用范围。
- 输入产物及 Schema。
- 操作步骤和决策规则。
- 输出产物及 Schema。
- 必须执行的验证。
- 失败和信息不足时如何处理。
- 正反例。
- 版本和兼容性。

Skill 应教授稳定的方法，不放入频繁变化的项目事实，也不堆大量百科资料。

### 12.3 Skill 选择

Workflow 节点明确声明首选 Skill，AgentOrchestrator 再根据项目配置、可用版本和依赖校验最终选择。第一阶段不让模型任意选择未知 Skill，避免执行路径不可控。

## 13. 知识库与“越来越聪明”

### 13.1 知识库分类

- **方法知识**：叙事结构、类型规律、对白、节奏、导演调度。
- **领域知识**：历史、法律、医学、地域文化等创作参考。
- **风格参考**：用户允许使用的风格描述和项目范例。
- **项目资料**：采访、设定、品牌手册和用户上传文档。
- **经验数据**：哪些产物被用户采纳、哪些问题经常被修改。

### 13.2 检索流程

```text
当前工作流节点
  -> 生成检索意图
  -> 按领域、来源、版本、许可和质量过滤
  -> 关键词/FTS 检索（MVP）
  -> 向量与混合检索（后续）
  -> 重排
  -> 注入少量相关片段
  -> 在 context_manifest 中记录引用
```

知识库内容不能整库塞给模型。剧本场景写作只获取与当前类型、人物关系和场景任务相关的片段。

### 13.3 知识增长闭环

“Agent 越来越聪明”不能等同于模型自行修改正式知识。采用受控闭环：

```text
发现知识缺口
  -> 搜索/导入候选资料
  -> 保存来源、版权和时间
  -> 提取候选知识卡片
  -> 去重、事实检查和质量评分
  -> 人工或规则审批
  -> 发布知识库新版本
  -> 在基准任务上评测
  -> 达标后供新项目使用
```

用户修改记录也不能直接当成通用知识。例如用户把一个喜剧结尾改成悲剧，只代表该项目偏好；只有多个项目反复出现并通过评审的方法，才可能沉淀为 Skill 或经验规则。

### 13.4 Skill 改进闭环

系统记录每次执行的输入、Skill 版本、输出、质量分、用户采用率和返工原因。定期形成 Skill 改进提案，通过离线评测比较新旧版本。只有新版本在连续性、完整性和用户采纳率上不退步，才进入发布。

这使“越来越好”成为可测量的工程过程，而不是无法验证的感觉。

## 14. 质量门禁与复杂情况

### 14.1 硬校验

- JSON Schema 是否有效。
- Episode、Scene、角色和道具引用是否存在。
- 集数、顺序和编号是否重复或缺失。
- 场景时长之和是否符合单集预算。
- 必填角色状态和连续性变更是否记录。
- 产物依赖版本是否仍然有效。

### 14.2 叙事质量评审

- 主角是否有明确目标、阻碍和选择。
- 每一集是否推动主线或角色变化。
- 冲突是否升级，转折是否有铺垫。
- 伏笔是否按计划回收。
- 角色行为是否符合已确认动机。
- 每集开场和结尾是否具有短剧钩子。
- 对白是否重复说明画面已经表达的信息。

叙事评审输出问题和证据，不直接宣布艺术作品“合格”。关键创意判断仍交给用户。

### 14.3 超长项目

- 按 Episode 或 Chapter 分批生产。
- 每批后生成不可丢失的状态快照。
- 主 Thread 保留项目决策；细节生产可使用辅助 Thread。
- 使用稳定 ID 和产物版本连接批次。
- 达到上下文阈值时可以压缩或更换 Thread，但先从 Canon 重建上下文。

### 14.4 并行编辑冲突

Artifact Version 使用乐观锁。生成时冻结依赖版本；提交时如果依赖已变化，则标记 `stale`，重新做影响分析，不能覆盖新版本。

### 14.5 Agent 输出不完整或格式错误

先进行结构修复 Turn；最多重试规定次数。仍失败时保留原始响应和错误报告，把节点置为 `review_required`，不发布半成品为正式版本。

### 14.6 用户推翻主线

重大方向修改默认创建 Branch，而不是破坏主线。用户比较两个版本后选择合并或替换。Codex Thread 分支和业务 Artifact 分支都必须登记，但二者不能假定天然一一对应。

### 14.7 外部研究与版权

检索资料必须记录来源、许可和引用位置。知识库保存摘要和必要事实，不复制大段受版权保护内容。风格学习使用抽象特征，避免要求模仿在世创作者的独特风格。

## 15. 数据库设计建议

### 15.1 通用核心表

| 表 | 用途 |
|---|---|
| `creative_projects` | 项目主表 |
| `project_threads` | 项目与 Codex Thread、角色和分支关系 |
| `workflow_definitions` | 工作流模板元数据和版本 |
| `workflow_runs` | 项目的一次流程运行 |
| `workflow_step_runs` | 节点执行、输入输出和状态 |
| `content_nodes` | Series/Episode/Scene/Shot 等通用内容树 |
| `artifacts` | 逻辑产物身份 |
| `artifact_versions` | 产物内容、文件、状态和来源 |
| `change_requests` | 用户修改及影响范围 |
| `quality_reports` | 规则和模型评审结果 |
| `agent_events` | 公开计划、进度、错误和执行事件 |

### 15.2 剧本领域表

| 表 | 用途 |
|---|---|
| `story_entities` | 角色、地点、道具、组织、事件 |
| `entity_relations` | 角色关系和实体间关系 |
| `continuity_facts` | 带生效区间和来源的连续性事实 |
| `narrative_threads` | 主线、支线、角色弧和伏笔 |
| `narrative_thread_beats` | 某条线在各集/场的推进与回收 |

### 15.3 Skill 与知识表

| 表 | 用途 |
|---|---|
| `skill_packages` | Skill 名称、版本、路径、校验和和状态 |
| `project_skill_bindings` | 项目固定使用哪些 Skill 版本 |
| `knowledge_documents` | 来源、许可、领域、质量和版本 |
| `knowledge_chunks` | 可检索片段及索引信息 |
| `knowledge_candidates` | 尚未审批的候选知识 |
| `execution_feedback` | 用户采用、返工和质量反馈 |

数据库不重复保存 Codex 的完整隐藏推理。只保存产品需要的公开过程、计划、调用记录、最终响应和可审计元数据。

## 16. 前端产品设计

### 16.1 创作台布局

- 左侧：项目和内容树，展开到集、场、镜头。
- 中间：当前产物编辑/预览区域，支持结构视图和剧本文本视图。
- 右侧或可折叠面板：Agent 对话、公开工作过程和修改建议。
- 顶部：当前工作流阶段、版本、模型和保存状态。
- 底部：提交创意、选择作用范围、附件和偏好。

### 16.2 用户交互模式

输入框不仅发送聊天，还带有明确作用范围：

- 整个项目。
- 故事圣经。
- 某一集。
- 某一场。
- 某个角色、道具或故事线。

Agent 对重大修改先显示影响范围。用户可以选择“只改本场”“同步调整后续”“创建备选分支”。

### 16.3 思考过程展示

前端展示的是可验证的公开工作过程：

- 正在读取哪些阶段产物。
- 当前执行哪个工作流节点。
- 正在检查哪些角色、伏笔和时长。
- 发现哪些连续性问题。
- 当前正在生成哪个产物。

完成后默认折叠，点击可查看。不能承诺或展示模型私有的完整思维链；App Server 提供的公开 reasoning summary 和 plan 可以作为补充事件。

## 17. 从剧本扩展到图片和视频

通用内核保持不变，只增加领域节点、Schema、Skill、适配器和校验器：

```text
剧本阶段
  screenplay -> scene -> character/prop/location references

分镜阶段
  scene -> shot_list -> shot

图片阶段
  shot -> visual_prompt -> image_generation_task -> image_asset

视频阶段
  approved_image/shot -> video_prompt -> video_generation_task -> video_asset

成片阶段
  video_asset + audio_asset -> timeline -> export
```

每个 Shot 继续引用同一批角色、服装、场景和道具实体，因此后续模型能够获得一致性约束。图片和视频调用复用现有 `generation_tasks`、`assets` 和 Provider Gateway；Workflow Step 只引用任务 ID，不自己轮询供应商。

不同领域包的统一契约：

```text
Domain Pack
  |- workflow definitions
  |- content node types
  |- artifact types and schemas
  |- skills
  |- validators
  |- renderers
  |- optional model tools
```

新增“小说”“广告”“分镜”“短剧制作”时，只注册新的 Domain Pack，不重写项目、版本、工作空间和执行内核。

## 18. 分阶段开发计划

### 阶段 0：设计确认

- 确认本设计中的项目、工作空间、Thread 和产物边界。
- 确认剧本层级和首版 Schema。
- 确认用户审批节点。
- 不开发业务功能。

### 阶段 1：通用创作项目骨架

- 建立 `creative_projects`、`project_threads`、`content_nodes`、`artifacts`、`artifact_versions`。
- 创建标准工作空间和 `project.json`。
- 一个项目绑定一个主 Codex Thread 和固定 `cwd`。
- 项目关闭和重启后可以恢复。

验收：创建项目、重启应用、再次进入项目，标题、阶段、Thread 和文件均能正确恢复。

### 阶段 2：结构化剧本 MVP

- 建立 Creative Brief、Story Bible、Series Outline、Episode Outline Schema。
- 使用 `outputSchema` 获取结构化结果。
- JSON 入库并渲染 Markdown。
- 前端展示项目树和阶段产物。

验收：一句猫的创意经过不超过三次关键提问，形成可确认的故事圣经和十集分集大纲。

### 阶段 3：单集完整剧本与连续性

- Scene 和 Screenplay Schema。
- 时长预算和硬校验。
- Story Entity、Continuity Fact 和 Narrative Thread。
- 一集一集生成，并携带相邻集状态。

验收：连续生成十集，每集有完整场景、角色和道具引用；自动发现预设的连续性冲突。

### 阶段 4：修改、版本和分支

- Change Request 和影响分析。
- Artifact 版本比较、审批和回滚。
- Codex `thread/fork` 与业务分支登记。
- 并发版本冲突保护。

验收：把关键道具回收从第三集改到第七集，只重写受影响内容，并给出完整影响报告。

### 阶段 5：Skill 与知识库

- 首批剧本 Skill。
- Skill 版本锁定、发现和显式调用。
- SQLite FTS5 知识检索。
- 知识候选、审批、版本和引用追踪。
- 基准剧本评测集。

验收：能够说明某个产物使用了哪些 Skill 和知识片段；升级 Skill 前后有可比较的质量报告。

### 阶段 6：分镜和多模态生产

- Shot 节点与分镜 Schema。
- 接入图片/视频 Generation Task。
- 角色、场景和道具一致性约束传递。
- 异步任务状态和资产回写工作流。

验收：从已批准剧本选一场生成分镜，再生成图片或视频；所有素材能追溯到场景、镜头、模型和任务。

## 19. 第一版明确不做

- 不让一个 Turn 一次生成并批准全部十集全文。
- 不把 Codex Thread 当作唯一数据库。
- 不让 Agent 直接无审计地修改正式产物。
- 不一开始建设复杂向量数据库，MVP 先用结构化过滤和 SQLite FTS5。
- 不自动把互联网内容写入正式知识库。
- 不在首版启用多 Agent 自由协商；先用明确工作流和有限辅助 Thread。
- 不在首版同时开发图片和视频，先把纯文本剧本闭环做可靠。

## 20. 需要确认的产品决策

进入开发前建议确认以下默认值：

1. 首个 MVP 是否以“10 集、每集 3 分钟竖屏短剧”为主要验收样例，同时兼容单集短片。
2. Story Bible、全季大纲和每集最终剧本是否都要求用户确认后才能进入下一阶段。
3. 用户修改已确认 Canon 时，是否默认先做影响分析，再允许提交。
4. 首版是否采用“数据库为应用事实源、工作空间为可移植镜像”的双重保存方式。
5. 首批 Skill 是否限定为故事架构、角色设计、分集设计、剧本写作和连续性审查五个。

以上五项确认后，阶段 1 和阶段 2 即可形成稳定的开发范围。
