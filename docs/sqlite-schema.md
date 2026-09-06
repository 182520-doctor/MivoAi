# 造境 SQLite 数据结构

日期：2026-09-06

## 设计原则

前端历史以造境自己的 SQLite 为准。Codex App Server 只负责生成回复和维持模型侧上下文，不能作为产品会话列表或消息详情的数据源。

## 表结构

### sessions

业务会话主表，对应前端左侧的会话列表。

- `id`：造境本地会话 ID，前端路由和接口使用它。
- `title`：会话标题，默认是“新的创意对话”，首次发送后更新为用户消息前 40 个字符。
- `codex_thread_id`：关联的 Codex App Server thread ID，仅用于继续上下文。
- `status`：`idle` 或 `running`。
- `created_at`、`updated_at`：创建和最近更新时间。

### turns

一次用户提交触发一个 turn，记录 Codex turn ID、推理过程和结果状态。

- `id`：造境本地 turn ID。
- `session_id`：所属业务会话。
- `codex_turn_id`：Codex App Server 返回的 turn ID。
- `status`：`running`、`completed`、`interrupted` 或 `failed`。
- `reasoning_text`：Codex 暴露的思考/推理文本。当前 App Server 有时只暴露 reasoning 生命周期和 token，不暴露完整文本。
- `reasoning_tokens`：Codex token usage 中的 `reasoningOutputTokens`。
- `error`：失败原因。
- `started_at`、`completed_at`：开始和完成时间。

### messages

前端消息详情表，也是页面历史的唯一来源。

- `id`：消息 ID。用户消息使用浏览器传入的 `clientMessageId`，助手消息由后端生成。
- `session_id`：所属业务会话。
- `turn_id`：所属 turn。
- `role`：`user` 或 `assistant`。
- `content`：消息正文，支持 Markdown/GFM。
- `status`：`streaming`、`done` 或 `error`。
- `created_at`、`updated_at`：创建和更新时间。

### submissions

浏览器提交幂等表，用来防止刷新、重试导致同一条消息重复生成。

- `id`：浏览器传入的 `clientMessageId`。
- `session_id`：所属业务会话。
- `status`：`started` 或 `finished`。
- `created_at`、`finished_at`：提交开始和结束时间。

## 读取路径

会话详情接口：

```text
GET /api/conversations/{conversation_id}/messages
```

只查询本地 `messages`，并通过 `turns` 关联返回助手消息的 `reasoning` 和 `reasoningTokens`。该接口不会调用 Codex 的 `thread/turns/list`。

## 写入路径

1. 浏览器提交消息。
2. 后端创建 `submissions`、`turns`、用户消息和助手占位消息。
3. Codex 流式返回 delta 时，后端追加更新助手消息 `content`。
4. Codex 返回 reasoning 事件或 token usage 时，后端更新 `turns.reasoning_text` 和 `turns.reasoning_tokens`。
5. turn 完成、失败或中断时，后端更新 `turns.status` 和助手消息状态。

