# 火山引擎接入记录

日期：2026-09-06
项目：`work/ai-dev-starter`

## 本次完成

- 增加 `model_providers`、`provider_credentials`、`models`、`user_preferences`、`generation_tasks`、`task_events` 表。
- 内置火山方舟供应商和已核对的文本、多模态、视频、图片模型目录。
- 接入火山方舟 Chat Completions 兼容接口：`POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`。
- 支持流式 `data:` 响应，统一转换为现有 SSE 事件：`meta`、`reasoning_delta`、`delta`、`done`。
- API Key 通过页面发送到本地 FastAPI，仅在本地后端以 Fernet 密文保存；日志、API 响应和前端状态不返回原始 Key。
- 文本调用在真正发送前写入 `generation_tasks.original_request_json`、`normalized_request_json`，并保存脱敏的 `provider_request_json`。
- 未配置火山 API Key 时，本地 Codex Agent 仍然可用。

## 页面操作

1. 打开 `http://127.0.0.1:3000`。
2. 点击输入框旁的模型按钮或设置图标。
3. 选择 `火山方舟 / Doubao Seed Evolving` 或 `Doubao Seed 2.1 Pro`。
4. 填入自己的 Ark API Key，点击保存。
5. 发送一条文本消息，页面会继续使用现有 SSE 展示流式结果。

## 当前边界

- `Seedance` 视频和 `Seedream` 图片已经进入模型目录，但状态为 `planned`，不会被文本入口误调用。
- 图片生成和视频异步轮询需要按火山方舟各自的 Image/Video API 单独实现，尚未宣称接通。
- 本地 Codex 的完整 thinking 文本展示仍受 App Server 实际事件能力影响；当前 SSE 链路保留并持续发送可用增量事件。

## 验证记录

- `uv run pytest -q`：11 passed
- `uv run ruff check app tests`：All checks passed
- `pnpm typecheck`：通过
- `pnpm build`：通过
- provider/catalog/task smoke：通过
