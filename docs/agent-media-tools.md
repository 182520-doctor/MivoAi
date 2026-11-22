# Agent 多模态工具

日期：2026-11-22

本地 Codex App Server 通过 `dynamicTools` 注册以下工具，并处理
`item/tool/call` 请求：

## 工具

### `zaojing_discover_media_models`

读取当前已启用且已配置的图片、视频或音频处理模型，返回公开参数契约和引用素材限制。
每次调用都会重新查询模型目录，因此后续启用的新工作流会自动出现。

### `zaojing_list_media_assets`

按图片、视频、音频或文件查询已有素材，返回素材 ID、来源、结果 URL 和任务关联。

### `zaojing_generate_media`

接收模型 ID、任务类型、提示词、业务参数和按模态分组的素材 ID 数组。工具内部创建
持久化任务并等待指定时间，返回任务 ID、状态和结果 URL。任务类型包括
`image_generation`、`video_generation`、`video_processing` 和
`audio_processing`。结果同时包含安全素材摘要，例如分离音频的
`originalFilename`，不暴露本地磁盘路径。

### `zaojing_get_media_task`

查询任务状态；可等待最多 120 秒。图片结果以 Markdown/API URL 返回给 Agent，
由 Agent 在最终回复中展示。

### `zaojing_retry_media_tasks`

从持久化的规范请求重试失败或已取消的媒体任务，一次最多 50 个。成功、运行中和
排队任务不会被重复提交。API 重启时，已经获得供应商任务 ID 的异步视频任务会恢复
轮询；只有无法安全确认的任务才标记为中断失败。

### `zaojing_list_speech_voices`

列出本机离线语音引擎可用音色，目前包括 `Microsoft Huihui Desktop / zh-CN`。

### `zaojing_synthesize_speech`

使用本机离线 TTS 生成音频。传入 `shotId` 时，工具会把结果自动写回该镜头的
`audioAssetId`。短剧角色实体可以保存 `voiceName` 和 `voiceRate`，Agent 应先读取
production 中的角色引用，再按说话角色选择音色。

### `zaojing_process_media`

执行确定性媒体处理：

- `extract_audio`：从视频中提取音轨；
- `upscale_video`：按项目画幅超分至 1080p。
- `normalize_audio`：执行双遍 EBU R128 响度分析和编码，默认目标为
  `-16 LUFS`、真峰值 `-1.5 dBTP`、响度范围 `11 LU`。
- `transcribe_audio`：使用本机 FFmpeg whisper.cpp 转写音频，返回带起止时间的
  cue 数组，并把规范 JSON 文件保存为素材。

传入 `shotId` 时自动更新镜头的音频或视频资产。

### `zaojing_list_drama_projects`

查询本地短剧项目、当前阶段和基础记录。

### `zaojing_get_drama_production`

读取短剧项目的分集、场次和镜头，包括镜头视频、音频、字幕与成片状态。

### `zaojing_get_drama_series`

读取项目级多集视频生产总览。工具按集返回计划、场次、镜头、关键帧、视频、审核与
成片覆盖率，并给出每集唯一的 `nextAction`：

`complete_plan`、`breakdown`、`generate_keyframes`、`generate_videos`、
`review_shots`、`render_episode` 或 `completed`。

返回值同时包含每集独立的派生质量门、缺失关键帧/视频/待审镜头、资产覆盖和最新
ProductionRun 状态。多集项目先调用此工具定位缺口，再进入目标集的
`zaojing_get_drama_episode`，不要一次加载并混合所有集的镜头细节。

### `zaojing_get_drama_episode`

只读取一个分集的计划、场次、镜头、实体引用和完成状态。长剧集中做单集制作时应优先
使用该工具，避免把全部 20 集内容装入模型上下文。

### `zaojing_audit_drama_episode`

对单个分集执行确定性审核：检查时间、地点、人物、场景、故事节拍、画面/对白要求、
场次标题、镜头画面描述、时长、对白和资产引用。Agent 应根据错误清单修订草稿，并在
请求用户确认之前重新审核。

### `zaojing_get_drama_roles`

读取编剧、导演、场景师、定妆师、灯光师、场记、执行导演和剪辑/声音的专业职责、
输入、交付物、检查清单和审核标准。可以按阶段过滤。

### `zaojing_get_drama_control_room`

读取当前阶段质量门、角色审核结果、用户决定和结构化分集计划。
每个质量门返回当前 `revision`、`approvedRevision`、`stale` 和最后变更原因。
内容修订变化后，旧审核与旧用户审批不会被当作当前有效证据。

### `zaojing_save_drama_draft`

保存 Brief、故事圣经或剧本的 Agent 草稿。该工具不会把文档标记为用户已批准。

### `zaojing_audit_drama_script`

对最新剧本执行确定性检查：是否存在正文、分集标题、场次标题、标准对白、重复集号和
占位文本。还会输出 `sceneCraft` 与 `craftSummary`：无动作的纯对白场、超长台词、
连续对白过长、重复台词和平均台词长度。Agent 应结合
`professional-story-production` playbook 自主修订，处理明确问题并重新审核后，才能
提交可审核版本。

### `zaojing_plan_drama_episodes`

创建或更新结构化分集计划，字段包括时间、地点、内外景、人物、场景、故事节拍、
画面检查、对白检查和连续性风险。每集还应提供 `sceneContracts`：逐场记录进入价值、
人物目标、障碍、战术、节拍、转折、退出价值、潜台词、表演、视觉和声音策略。

场景契约是导演拆镜、表演设计、关键帧和视频提示词的共同上游。缺失契约会产生
`episode_scene_contracts_missing` 审核警告；契约编号重复或引用不存在的场次也会被
确定性检查发现。

ProductionRun 组装首帧、尾帧、九宫格、故事板和视频任务时，会自动读取镜头所属场次的
契约，把价值变化、人物目标、障碍、战术、节拍、转折、潜台词、声台形表、视觉和声音
策略加入生成提示词。前端单镜关键帧与视频生成使用同一规则。

### `zaojing_plan_drama_shots`

为尚无场次的分集创建场次和镜头。工具会拒绝覆盖用户已经编辑过的拆解。

### `zaojing_plan_drama_assets`

创建或更新角色、服装、道具、场景和风格资产，并写入角色设定总表、场景总图、
内外景、灯光和材质等语义槽位。

角色实体的 `profile` 保存人物创作档案：外在目标、内在需求、创伤、错误信念、恐惧、
性格矛盾、公开面具、私下自我、语言习惯、声音、形体行为、人物弧光和连续性规则。
Agent 应主动创建和维护这些字段，用户只需要审核人物是否可信、可演和前后一致。

角色的 `character_sheet` 是一张 16:9 连续画布，同一张图内包含头部与面部特写、
全身正面/侧面/背面、表情特写以及服装纹样与材质细节。它不再拆成多张独立视图；
后续镜头只引用这一张总表和主视觉，降低身份和造型漂移。

### `zaojing_bind_drama_asset`

把生成或上传的素材绑定回制作图谱：

- `targetType=entity`：`primary`、`reference`、角色设定总表、场景总图/内外景、
  道具、服装和风格槽位；
- `targetType=shot`：`first_frame`、`last_frame`、`grid9`、`storyboard`、
  `video`、`audio`。

图片槽位只接受图片，视频和音频槽位分别校验素材类型。该工具让
`zaojing_generate_media` 的结果真正进入持久化短剧状态，而不是停留在聊天附件。
每次绑定都会同时写入候选账本；替换主槽位不会删除旧结果。

### `zaojing_update_drama_shot_prompt`

保存镜头槽位的持久提示词版本，覆盖 first_frame、last_frame、grid9、storyboard、
video 或 audio。提示词会参与阶段修订，修改后旧审核和审批失效；批量规划与单镜生成
都会优先使用保存版本。

### `zaojing_update_drama_shot_direction`

持久化镜头级导演设计：景别、机位角度、镜头运动、焦段、人物调度、表演动作、表情、
构图、灯光、声音、转场和参考说明。修改镜头设计会使原有镜头审核失效，并自动进入
首帧、尾帧、九宫格、故事板和视频提示词。

分集审核会汇总缺失结构化导演设计的镜头。Agent 应以场景契约、对白和资产为依据先
完成镜头设计，再请求关键帧或视频生成。

### `zaojing_update_drama_entity_prompt`

保存角色、场景、服装、道具或风格实体的专业槽位提示词。批量资产规划会优先复用
保存版本；修改提示词会使资产及下游阶段修订失效。

### `zaojing_set_drama_shot_status`

对单个镜头执行状态流转。没有视频的镜头不能标记为 approved；替换或重新候选视频后
会自动回到 clip_ready，必须重新审核，避免旧镜头批准沿用到新视频。

### `zaojing_get_drama_shot_history`

读取镜头不可变状态历史，包含修改前状态、修改后状态、审核者、说明和时间。用户审核、
Agent 审核以及素材替换触发的系统退回都会被记录。

### `zaojing_list_drama_asset_candidates`

读取项目、实体或镜头槽位的持久候选历史。候选状态包括：

- `selected`：当前槽位正在使用；
- `superseded`：曾经使用，后来被替换；
- `candidate`：等待选择；
- `rejected`：人工或 Agent 明确弃用。

镜头候选覆盖首帧、尾帧、九宫格、故事板、视频和音频；实体候选覆盖主视觉、
专业资产槽位和补充参考。任务完成、页面刷新或应用重启后历史都不会消失。

### `zaojing_update_drama_asset_candidate`

选择、恢复或弃用一个候选。选择候选会同时更新实体或镜头的语义槽位；当前主素材
不能直接弃用，必须先选择其他候选，避免制作图谱出现无意的空槽位。

### `zaojing_create_drama_production_run`

为一个分集创建持久化批量制作运行。每个制作项包含目标实体/镜头、语义槽位以及完整的
规范媒体请求。创建只生成任务图，不立即占用 GPU。运行支持资产、分镜关键帧和镜头视频
三个阶段，每个运行最多 100 项、并行数 1–4。

### `zaojing_plan_drama_production_run`

根据一个分集当前真实数据自动组装 ProductionRun，而不是让 Agent 手写几十个镜头项。
规划器会：

- 读取分集镜头、实体引用、已绑定素材和缺失槽位；
- 应用所选模型的默认参数、画面比例和参考图上下限；
- 自动排序角色、服装、场景、首尾帧、九宫格和故事板参考；
- 为每个目标生成可追溯提示词和规范媒体请求；
- 跳过参考素材不足的项，并把原因回传给 Agent；
- 只创建待审任务图，不启动 GPU。

Agent 必须把生成项数量、跳过项、模型和预计范围展示给用户，再请求确认启动。

资产阶段实施主图引导规则：实体没有 primary 或可用参考图时，只允许先规划
`primary`；角色设定总表、内外景和细节槽位必须等待主图产出后，改用支持图片参考
的模型生成，不能把多次纯文生图结果冒充同一身份。

规划器同时把 `planning.source`、选用模型、模型参数和 skipped reasons 写入
ProductionRun。刷新页面或 API 重启后，制作控制室仍能看到“为什么是这些任务、为什么
有些槽位没有进入本批次”，而不是只在一次 Agent 回复里可见。

资产主图任务成功后会经过同一实体语义槽位绑定流程，并推进资产阶段修订，使旧角色
审核自动失效。回归测试覆盖了“媒体成功 → primary 绑定 → 阶段修订增加”的完整链路。

ProductionRun 提交媒体任务时会把项目、分集、运行、目标和语义槽位写入
`original_request.origin`。任务中心据此显示短剧 lineage，生成任务可从任务记录追溯
回具体资产或镜头，而不必手工比对提示词。

### `zaojing_start_drama_production_run`

在用户明确确认任务数量、模型和成本后启动运行。成功项固定媒体任务 ID 和结果素材；
失败项不会阻止其他项完成。Agent 不得未经确认自行启动昂贵批量生成。

### `zaojing_get_drama_production_run`

读取运行状态、每项任务 ID、结果素材和错误。用于报告进度、定位失败项和判断是否可以
进入阶段审核。

### `zaojing_retry_drama_production_failures`

只重置并重试失败项。已成功项及其绑定素材保持不变，因此可从部分失败状态断点继续。

### `zaojing_cancel_drama_production_run`

取消运行；当前已经提交的媒体请求可以继续到完成，后续未开始项不再提交。

### `zaojing_review_drama_stage`

让某个专业角色记录阶段审核结果。Agent 的通过只是专业检查证据，阶段放行仍由用户
确认。

### `zaojing_audit_drama_project`

执行连续性检查：未锁定资产、缺视频、缺音频、镜头未关联角色/场景、角色未配置
音色、对白缺字幕等，并返回评分、错误数和警告数。

### `zaojing_render_episode`

按当前镜头视频、配音、字幕、转场和混音设置合成整集，返回持久化
`exportAssetId`。该工具不会绕过镜头缺失校验。
默认还会校验每一镜 `approved`；`strictApprovals=false` 只能用于用户明确要求的
未审核预览，不能用它冒充最终成片。
每次渲染还会生成不可变 export manifest，记录阶段修订、文档版本、实体槽位、
镜头媒体、字幕、混音和审批告警；Agent 只接收清单 ID 与摘要，避免把完整血缘塞满
上下文。

### `zaojing_list_drama_export_manifests`

读取一个分集的不可变成片血缘清单。用于回答某版成片使用了哪些剧本、资产、首尾帧、
镜头视频、音频和审批修订，也可用于比较两次渲染之间输入是否变化。

## Agent 决策流程

1. 理解用户要的是图片、视频、配音、媒体处理还是短剧成片；
2. 调用发现工具查询当前真实可用模型；
3. 根据能力、参数契约和引用限制选择模型；
4. 需要已有参考图时查询素材 ID；
5. 使用统一语义参数组装请求并创建任务；
6. 等待任务，必要时查询状态；
7. 在最终回复中展示图片、视频链接和任务信息。

短剧任务先读取 control room 和角色手册，再查询 production，不在模型上下文中伪造
项目、场次、镜头或资产 ID。生成结果必须通过 `zaojing_bind_drama_asset` 回到对应
语义槽位。在昂贵生成或整集渲染前调用 `zaojing_audit_drama_project`，先处理明确的
连续性错误和警告。

Agent 是专业制作的主执行者。确认一次故事命题、受众、集数、时长、内容边界和视觉
方向后，编剧、导演、场景、定妆、分镜和视频工作由 Agent 直接完成、自审和修订；
用户主要审核、否决、要求重做或批准阶段。不要把专业字段重新变成用户必填表单，也不
要在每个小步骤反复打断用户。具体场景契约、对白、潜台词、声台形表、分镜、轴线和
质量门读取 `playbooks/professional-story-production.md`。

当前迭代以完整多集镜头视频为第一目标。字幕、剪辑、配音和整集包装继续保留现有
能力与接口，但不作为本阶段自动推进条件。多集续作必须先调用
`zaojing_get_drama_series`，按集选择下一步；每一集单独规划、单独审核、单独确认
ProductionRun，不能把一集的素材或任务状态套到另一集。

## 会话 workspace

`CODEX_WORKSPACE` 是所有会话 workspace 的根目录，默认是 `runtime/chat`：

```text
runtime/chat/
├── shared/
│   ├── AGENTS.md
│   ├── playbooks/
│   └── tools/
└── sessions/
    └── <conversation-id>/
        └── README.md
```

- 每个本地 conversation 有独立目录；
- Codex thread 的 `cwd` 指向该 conversation 目录；
- `runtimeWorkspaceRoots` 同时包含会话目录和共享目录；
- 共享 playbook 和工具说明通过 `zaojing_get_shared_context` 读取；
- 数据库保存 `codex_thread_id`、`workspace_path` 和 `tool_runtime_version`；
- 应用重启后按原 thread ID 恢复，并把原 workspace `cwd` 传给
  `thread/resume`。

## 线程升级

旧 Codex 线程不支持后补 `dynamicTools` 或会话级 workspace。当
`sessions.tool_runtime_version` 小于当前版本时，下一条消息会创建带当前工具和新 workspace
的 Codex 线程，同时继续使用 SQLite 中的本地产品历史。
