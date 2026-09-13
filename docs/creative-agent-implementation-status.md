# 创作 Agent 当前实现状态

## 已完成

- 创建创作项目并分配独立工作空间。
- 为项目保存主导演 Codex Thread。
- 创作消息携带 `projectId`。
- Codex Thread 使用项目目录作为 `cwd`。
- 创作项目使用 `workspace-write` 沙盒。
- Agent 默认自动补全普通信息并连续执行。
- 只有重大歧义、方向冲突或明确要求时才询问用户。
- Codex Turn 完成后扫描阶段 Markdown 文件。
- 文件变化写入 `creative_artifact_versions`。
- 同步工作流步骤和项目状态。
- 通过 WebSocket 推送项目同步事件。
- 前端创建项目后自动启动 Agent。

## 当前运行链路

```text
用户提交创意
  -> 创建项目
  -> 创建工作空间和初始产物
  -> 自动生成项目 Prompt
  -> 自动启动 Codex Turn
  -> Codex 读取项目规则和文件
  -> Codex 写入阶段产物
  -> 后端扫描文件并计算哈希
  -> SQLite 保存产物版本
  -> 更新工作流状态
  -> 前端展示同步结果
```

## 尚未完成

- 每个阶段独立的结构化 JSON Schema。
- 阶段输出的严格校验和失败重试。
- 故事人物、道具、地点和时间线的连续性检查。
- 草案、审核、正式发布的完整审批状态。
- 修改前序设定后的影响分析。
- 多轮长任务的后台队列和断点恢复。
- Skill Registry 和知识库检索。

## 验收方式

1. 启动前后端服务并打开首页。
2. 在“小说 Agent 工作流”输入创意，点击生成草稿。
3. 创建成功后不需要再次点击聊天发送，Agent 会自动开始。
4. 观察聊天中的公开进度和最终回复。
5. 检查项目工作空间中的 `exports/novel.md` 和 `exports/novel-project.md`。
6. 检查 SQLite 中的 `creative_artifacts`、`creative_artifact_versions`
   和 `workflow_step_runs` 是否有更新。
