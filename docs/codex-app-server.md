Codex app-server 是 Codex 为功能丰富的客户端（例如 Codex VS Code 扩展程序）提供支持的接口。如果您希望在自己的产品中深度集成 Codex，包括身份验证、对话历史记录、审批和智能体事件流，请使用此接口。app-server 的实现已在 Codex GitHub 代码仓库（[openai/codex/codex-rs/app-server](https://github.com/openai/codex/tree/main/codex-rs/app-server)）中开源。有关 Codex 开源组件的完整列表，请参阅[开源](/zh-Hans/codex/open-source)页面。


  如果您要自动执行作业或在 CI 中运行 Codex，请改用
<a href="/codex/codex-sdk">Codex SDK</a>。


## 连接 CLI 终端界面

远程终端界面模式允许您在一台计算机上运行 app-server，并从另一台计算机通过 Codex CLI 终端界面连接它。
启动 WebSocket 侦听器：

```bash
codex app-server --listen ws://127.0.0.1:4500
```

然后连接终端界面：

```bash
codex --remote ws://127.0.0.1:4500
```

对于非本地连接，请配置 WebSocket 身份验证，并使用 TLS 保护连接。
将不记名 Token 存入环境变量，
然后传递变量名称，而不要将 Token 放在命令行中：

```bash

codex --remote wss://remote-host:4500 \
  --remote-auth-token-env CODEX_REMOTE_TOKEN
```

`--remote` 选项接受 `ws://`、`wss://`、`unix://` 和
`unix://PATH` 端点。未加密的 WebSocket 仅可用于 localhost 或
SSH 端口转发连接。

## 连接远程代码模式主机

默认情况下，app-server 会启动本地代码模式主机。
如需改用远程主机，请传递其安全 WebSocket URL：

```bash
codex app-server --code-mode-host wss://code-mode.example.com/host
```

`--code-mode-host` 控制 app-server 到其代码模式主机的出站连接。
此选项不会更改 `--listen`；后者控制客户端连接 app-server 的方式。
同一 app-server 进程中的所有线程
共享所选的代码模式主机连接。

远程主机应使用 `wss://`。`ws://` 仅可用于 localhost 或
SSH 转发连接。app-server 命令和 WebSocket 传输均处于实验阶段，
不支持用于生产工作负载。

## 协议

与 [MCP](https://modelcontextprotocol.io/) 类似，`codex app-server` 支持使用 JSON-RPC 2.0 消息进行双向通信（传输时会省略 `"jsonrpc":"2.0"` 标头）。

支持的传输方式：

- `stdio`（`--listen stdio://`，默认）：以换行符分隔的 JSON（JSONL）。
- `websocket`（`--listen ws://IP:PORT`，实验性且不受支持）：每个 WebSocket 文本帧包含一条
  JSON-RPC 消息。
- Unix 套接字（`--listen unix://` 或 `--listen unix://PATH`）：通过 Codex 默认的 app-server 控制套接字或自定义 Unix 套接字路径建立
  WebSocket 连接，
  使用标准 HTTP Upgrade 握手。
- `off`（`--listen off`）：不开放本地传输接口。

使用 `--listen ws://IP:PORT` 运行时，同一侦听器还会提供基本的
HTTP 健康探测：

- 侦听器开始接受新连接后，`GET /readyz` 会返回 `200 OK`。
- 当请求不包含 `Origin` 标头时，
  `GET /healthz` 会返回 `200 OK`。
- 包含 `Origin` 标头的请求会被拒绝，并返回 `403 Forbidden`。

WebSocket 传输属于实验性功能，且不受支持。
`ws://127.0.0.1:PORT` 这样的本地侦听器适用于 localhost 和 SSH 端口转发工作流。
在当前的逐步推出阶段，非环回 WebSocket 侦听器
默认允许未经身份验证的连接，因此在将其开放给远程访问之前，
请先配置 WebSocket 身份验证。

支持的 WebSocket 身份验证标志：

- `--ws-auth capability-token --ws-token-file /absolute/path`
- `--ws-auth capability-token --ws-token-sha256 HEX`
- `--ws-auth signed-bearer-token --ws-shared-secret-file /absolute/path`

对于已签名的不记名 Token，您还可以设置 `--ws-issuer`、`--ws-audience` 和
`--ws-max-clock-skew-seconds`。客户端在 WebSocket 握手期间以
`Authorization: Bearer <token>` 的形式提供凭据，app-server 会在处理
JSON-RPC `initialize` 之前强制进行身份验证。

请优先使用 `--ws-token-file`，不要在命令行中传递原始不记名 Token。
只有当客户端将原始高熵 Token 保存在独立的本地机密存储中时，
才应使用 `--ws-token-sha256`；哈希值仅用于验证，
客户端仍需原始 Token。

在 WebSocket 模式下，app-server 使用有界队列。当请求入口队列已满时，
服务器会拒绝新请求，并返回 JSON-RPC 错误代码 `-32001` 和消息
`"Server overloaded; retry later."`。客户端应在重试时采用指数递增的延迟，
并加入随机抖动。

## 消息模式

请求包含 `method`、`params` 和 `id`：

```json
{ "method": "thread/start", "id": 10, "params": { "model": "gpt-5.6-terra" } }
```

响应会回显 `id`，并包含 `result` 或 `error`：

```json
{ "id": 10, "result": { "thread": { "id": "thr_123" } } }
```

```json
{ "id": 10, "error": { "code": 123, "message": "Something went wrong" } }
```

通知会省略 `id`，仅使用 `method` 和 `params`：

```json
{ "method": "turn/started", "params": { "turn": { "id": "turn_456" } } }
```

您可以通过 CLI 生成 TypeScript 模式或 JSON Schema 包。每份输出都对应您运行的 Codex 版本，因此生成的产物与该版本完全匹配：

```bash
codex app-server generate-ts --out ./schemas
codex app-server generate-json-schema --out ./schemas
```

## 入门

1. 使用 `codex app-server`（默认 stdio 传输）、
`codex app-server --listen ws://127.0.0.1:4500`（TCP WebSocket）或
`codex app-server --listen unix://`（默认 Unix 套接字）启动服务器。
2. 通过所选传输方式连接客户端，然后发送 `initialize`，再发送 `initialized` 通知。
3. 启动一个线程和一个轮次，然后持续从当前活动的传输流中读取通知。

示例（Node.js / TypeScript）：

```ts



const proc = spawn("codex", ["app-server"], {
  stdio: ["pipe", "pipe", "inherit"],
});
const rl = readline.createInterface({ input: proc.stdout });

const send = (message: unknown) => {
  proc.stdin.write(`${JSON.stringify(message)}\n`);
};

let threadId: string | null = null;

rl.on("line", (line) => {
  const msg = JSON.parse(line) as any;
  console.log("server:", msg);

  if (msg.id === 1 && msg.result?.thread?.id && !threadId) {
    threadId = msg.result.thread.id;
    send({
      method: "turn/start",
      id: 2,
      params: {
        threadId,
        input: [{ type: "text", text: "Summarize this repo." }],
      },
    });
  }
});

send({
  method: "initialize",
  id: 0,
  params: {
    clientInfo: {
      name: "my_product",
      title: "My Product",
      version: "0.1.0",
    },
  },
});
send({ method: "initialized", params: {} });
send({ method: "thread/start", id: 1, params: { model: "gpt-5.6-terra" } });
```

## 核心基元

- **线程**：用户与 Codex 智能体之间的一段对话。线程包含轮次。
- **轮次**：一次用户请求及智能体随后执行的工作。轮次包含条目，并以流式方式发送增量更新。
- **条目**：输入或输出的一个单元，包括用户消息、智能体消息、命令执行、文件更改、工具调用等。

使用线程 API 创建、列出或归档对话。使用轮次 API 推进对话，并通过轮次通知以流式方式获取进度。

## 生命周期概览

- **每个连接仅初始化一次**：打开传输连接后，立即发送包含客户端元数据的 `initialize` 请求，然后发送 `initialized`。完成此握手前，服务器会拒绝该连接上的任何请求。
- **启动或恢复线程**：调用 `thread/start` 创建新对话，调用 `thread/resume` 继续现有对话，或调用 `thread/fork` 基于历史记录派生出具有新 ID 的线程。
- **开始轮次**：调用 `turn/start`，并提供目标 `threadId` 和用户输入。可选字段可以覆盖模型、个性、`cwd`、沙盒策略等设置。
- **引导进行中的轮次**：调用 `turn/steer`，将用户输入追加到当前正在进行的轮次，无需创建新轮次。
- **流式接收事件**：调用 `turn/start` 后，持续从 stdout 读取通知，包括 `thread/archived`、`thread/unarchived`、`item/started`、`item/completed`、`item/agentMessage/delta`、工具进度及其他更新。
- **结束轮次**：模型完成工作或通过 `turn/interrupt` 取消轮次后，服务器会发出包含最终状态的 `turn/completed`。

## 初始化

客户端必须在每个传输连接上调用任何其他方法之前，先发送且仅发送一次 `initialize` 请求，然后通过 `initialized` 通知确认。初始化前发送的请求会收到 `Not initialized` 错误；在同一连接上重复调用 `initialize` 会返回 `Already initialized`。

服务器会返回其向上游服务提供的用户代理字符串，以及描述运行目标平台的 `platformFamily` 和 `platformOs` 值。设置 `clientInfo` 以标识您的集成。

`initialize.params.capabilities` 还支持以下客户端能力：

- `optOutNotificationMethods`：指定在此连接上要屏蔽的通知方法的确切名称。
  仅支持精确匹配，不支持通配符或前缀匹配；
  未知名称会被接受但忽略。
- `requestAttestation`：主动启用由服务器发起的 `attestation/generate` 请求。
  向上游提供证明的桌面主机会返回一个不透明的
  `{ "token": "..." }` 值。
- `mcpServerOpenaiFormElicitation`：允许下游 MCP 服务器发送
  `mcpServer/elicitation/request` 的 OpenAI 扩展表单变体。

**重要**：使用 `clientInfo.name` 在合规日志平台中标识您的客户端。如果您正在开发供企业使用的新 Codex 集成，请联系 OpenAI，将其加入已知客户端列表。有关更多背景信息，请参阅[Codex 日志参考资料](https://chatgpt.com/public/admin/api-reference#tag/Codex)。

示例（来自 Codex VS Code 扩展程序）：

```json
{
  "method": "initialize",
  "id": 0,
  "params": {
    "clientInfo": {
      "name": "codex_vscode",
      "title": "Codex VS Code Extension",
      "version": "0.1.0"
    }
  }
}
```

屏蔽通知的示例：

```json
{
  "method": "initialize",
  "id": 1,
  "params": {
    "clientInfo": {
      "name": "my_client",
      "title": "My Client",
      "version": "0.1.0"
    },
    "capabilities": {
      "experimentalApi": true,
      "optOutNotificationMethods": ["thread/started", "item/agentMessage/delta"]
    }
  }
}
```

## 启用实验性 API

部分 app-server 方法和字段按设计需启用 `experimentalApi` 能力后才能使用。

- 若要仅使用稳定的 API 接口，请省略 `capabilities`，或将 `experimentalApi` 设置为 `false`；服务器会拒绝实验性方法或字段。
- 将 `capabilities.experimentalApi` 设置为 `true`，以启用实验性方法和字段。

```json
{
  "method": "initialize",
  "id": 1,
  "params": {
    "clientInfo": {
      "name": "my_client",
      "title": "My Client",
      "version": "0.1.0"
    },
    "capabilities": {
      "experimentalApi": true
    }
  }
}
```

如果客户端在未主动启用的情况下发送实验性方法或字段，app-server 会拒绝该请求并返回：

`<descriptor> requires experimentalApi capability`

## API 概览

- `thread/start`：创建新线程；发出 `thread/started`，并自动为您订阅该线程的轮次和项事件。
- `thread/resume`：按 ID 重新打开现有线程，使后续 `turn/start` 调用向其中追加内容。
- `thread/fork`：通过复制已存储的历史记录，派生出具有新线程 ID 的线程。传入 `lastTurnId` 可复制截至该轮次（含该轮次）的历史记录并省略后续轮次，或传入 `ephemeral: true` 创建内存中的派生线程。为新线程发出 `thread/started`；返回的线程在可用时包含 `forkedFromId`。
- `thread/read`：按 ID 读取已存储的线程而不恢复该线程；设置 `includeTurns` 可返回完整的轮次历史记录。返回的 `thread` 对象包含运行时 `status`。
- `thread/list`：分页浏览已存储的线程日志；支持基于游标的分页，以及 `modelProviders`、`sourceKinds`、`archived`、`isPinned`、`cwd`、`useStateDbOnly`、`searchTerm` 和实验性的 `parentThreadId` 或 `ancestorThreadId` 筛选条件。返回的 `thread` 对象包含运行时 `status`。
- `thread/turns/list`：实验性方法；在不恢复线程的情况下，分页浏览其已存储的轮次历史记录。`itemsView` 用于控制是省略轮次项、返回其摘要，还是完整加载这些项。
- `thread/items/list`：实验性方法；分页浏览持久化的线程项，可选择将结果限制为单个 `turnId` 对应的项。当前使用的线程存储必须支持项分页。
- `thread/loaded/list`：列出当前已加载到内存中的线程 ID。
- `thread/name/set`：为已加载线程或持久化线程记录设置或更新面向用户的线程名称；发出 `thread/name/updated`。
- `thread/goal/set`：设置线程目标；发出 `thread/goal/updated`。
- `thread/goal/get`：读取线程的当前目标。
- `thread/goal/clear`：清除线程目标；发出 `thread/goal/cleared`。
- `thread/metadata/update`：局部更新存储在 SQLite 中的线程元数据，包括已持久化的 `gitInfo` 和 `isPinned`。
- `thread/archive`：将线程的日志文件移入归档目录，并尝试归档其生成的后代线程中尚未归档的日志；成功时返回 `{}`，并为每个已归档线程发出 `thread/archived`。
- `thread/delete`：永久删除持久化的活动线程或已归档线程及其生成的所有后代线程；成功时返回 `{}`，并为每个已删除线程发出 `thread/deleted`。
- `thread/unsubscribe`：取消此连接对线程轮次和项事件的订阅。如果此连接是最后一个订阅者，服务器会在线程无订阅者且无活动的宽限期结束后卸载该线程，并发出 `thread/closed`。
- `thread/unarchive`：将已归档的线程记录恢复到活动会话目录；返回恢复后的 `thread`，并发出 `thread/unarchived`。
- `thread/status/changed`：已加载线程的运行时 `status` 发生变化时发出的通知。
- `thread/compact/start`：触发线程的对话历史记录压缩；立即返回 `{}`，同时通过 `turn/*` 和 `item/*` 通知以流式方式传输进度。
- `thread/shellCommand`：针对线程运行由用户发起的 shell 命令。该命令在沙盒外以完全访问权限运行，且不继承线程的沙盒策略。
- `thread/backgroundTerminals/clean`：停止某个线程所有正在运行的后台终端（实验性；需要 `capabilities.experimentalApi`）。
- `thread/backgroundTerminals/list`：列出已加载线程中正在运行的后台终端（实验性；需要 `capabilities.experimentalApi`）。
- `thread/backgroundTerminals/terminate`：使用 app-server 的 `processId` 终止一个正在运行的后台终端（实验性；需要 `capabilities.experimentalApi`）。
- `thread/rollback`：已弃用；从内存上下文中移除最后 N 个轮次，并持久化回滚标记；返回更新后的 `thread`。
- `turn/start`：向线程添加用户输入或独立的工具输出，让 Codex 开始生成；返回初始 `turn`，并流式传输事件。对于 `collaborationMode`，`settings.developer_instructions: null` 表示“使用所选模式的内置指令”。
- `thread/inject_items`：将原始 Responses API 项追加到已加载线程中模型可见的历史记录，而不启动用户轮次。
- `turn/steer`：将用户输入追加到线程当前正在进行的轮次；返回接受该输入的轮次的 `turnId`。
- `turn/interrupt`：请求取消正在进行的轮次；成功时返回 `{}`，该轮次以 `status: "interrupted"` 结束。
- `review/start`：为线程启动 Codex 审查器；发出 `enteredReviewMode` 项和 `exitedReviewMode` 项。
- `command/exec`：在服务器沙盒内运行单条命令，而不启动线程或轮次。
- `command/exec/write`：向正在运行的 `command/exec` 会话的 `stdin` 写入字节数据，或关闭 `stdin`。
- `command/exec/resize`：调整正在运行且使用 PTY 的 `command/exec` 会话的终端大小。
- `command/exec/terminate`：停止正在运行的 `command/exec` 会话。
- `command/exec/outputDelta`（通知）：当流式 `command/exec` 会话产生经过 base64 编码的 stdout/stderr 数据块时发出。
- `process/spawn`：在 Codex 沙盒外显式启动一个进程会话（实验性；需要 `capabilities.experimentalApi`）。
- `process/writeStdin`：向正在运行的 `process/spawn` 会话的 stdin 写入字节数据，或关闭 stdin（实验性）。
- `process/resizePty`：调整正在运行且使用 PTY 的进程会话的终端大小（实验性）。
- `process/kill`：终止正在运行的进程会话（实验性）。
- `process/outputDelta` 和 `process/exited`（通知）：分别用于传输流式进程输出和进程退出状态（实验性）。
- `model/list`：列出可用模型（设置 `includeHidden: true` 可包含满足 `hidden: true` 条件的条目），同时返回推理强度选项、可选的 `upgrade` 和 `inputModalities`。
- `modelProvider/capabilities/read`：读取模型与提供商组合对应的提供商能力限制。
- `experimentalFeature/list`：列出功能标志及其生命周期阶段元数据，并支持游标分页。
- `experimentalFeature/enablement/set`：针对 `apps` 和 `plugins` 等受支持的功能键，局部更新内存中的运行时设置。
- `environment/info`：实验性方法；连接到已配置的执行环境，并返回其 shell 和默认工作目录。
- `permissionProfile/list`：列出 Beta 版权限配置方案，以及当前生效的要求是否允许使用这些方案，并支持游标分页。
- `collaborationMode/list`：列出协作模式预设（实验性，不支持分页）。
- `skills/list`：列出一个或多个 `cwd` 值对应的技能（支持 `forceReload`，并可选用 `perCwdExtraUserRoots`）。
- `skills/extraRoots/set`：替换用于发现独立技能的进程级额外根目录，但不持久化这些根目录设置。
- `skills/changed`（通知）：受监视的本地技能文件发生更改时发出。
- `hooks/list`：列出针对一个或多个 `cwd` 值发现的生命周期钩子。
- `marketplace/add`：添加远程插件市场，并将其持久化到用户的市场配置中。
- `marketplace/remove`：移除已配置的市场；若其安装根目录存在，也一并移除。
- `marketplace/upgrade`：刷新已配置的 Git 市场；如果省略市场名称，则刷新所有已配置的 Git 市场。
- `plugin/list`：正在开发中；列出发现的插件市场和插件状态，包括安装和身份验证策略元数据、市场加载错误、精选插件 ID，以及本地、Git、软件包注册表或远程插件的来源元数据。摘要可包含远程 `version`、本地 `localVersion`、以结构化形式提供的浅色和深色图标，以及 `installPolicySource`；对于当前远程条目，后者可以是 `null`、`WORKSPACE_SETTING` 或 `IMPLICIT_CANONICAL_APP`。请暂勿从生产客户端调用此方法。
- `plugin/read`：正在开发中；根据市场路径或远程市场名称，结合插件名称读取单个插件，包括捆绑的技能、应用和 MCP 服务器名称。如果远程目录提供远程插件的 `shareUrl`，也会一并返回。请暂勿从生产客户端调用此方法。
- `plugin/install`：正在开发中；根据市场路径或远程市场名称安装插件。请暂勿从生产客户端调用此方法。
- `plugin/uninstall`：正在开发中；卸载已安装的插件。请暂勿从生产客户端调用此方法。
- `plugin/skill/read`：根据远程市场、插件 ID 和技能名称，按需读取远程插件技能的 Markdown。
- `app/installed`：读取已安装应用的运行时状态，包括每个应用实际生效的启用状态和可调用状态。
- `app/list`：列出可用应用（连接器），支持分页，并包含可访问状态和启用状态元数据。
- `app/read`：获取指定应用 ID 对应的元数据，以及可选的仅供显示的工具摘要。
- `skills/config/write`：按路径启用或禁用技能。
- `mcpServer/oauth/login`：为已配置的 MCP 服务器启动 OAuth 登录；返回授权 URL，并在完成时发出 `mcpServer/oauthLogin/completed`。
- `tool/requestUserInput`：针对工具调用向用户提出 1 至 3 个简短问题（实验性）；可为问题设置 `isOther`，以提供自由输入选项。
- `mcpServer/elicitation/request`（服务器请求）：请求客户端提供结构化表单输入，或确认 MCP 服务器请求的 URL 流程。
- `item/permissions/requestApproval`（服务器请求）：请求客户端授予内置 `request_permissions` 工具所请求的网络或文件系统权限的子集。
- `config/mcpServer/reload`：从磁盘重新加载 MCP 服务器配置，并将已加载线程的刷新操作加入队列。
- `mcpServerStatus/list`：列出 MCP 服务器、工具、资源和身份验证状态，支持基于游标和数量限制的分页。使用 `detail: "full"` 获取完整数据，或使用 `detail: "toolsAndAuthOnly"` 省略资源。
- `mcpServer/resource/read`：通过已初始化的 MCP 服务器读取单个 MCP 资源。
- `mcpServer/tool/call`：调用为线程配置的 MCP 服务器上的工具。
- `mcpServer/startupStatus/updated`（通知）：当已加载线程所配置的 MCP 服务器的启动状态发生变化时发出。
- `windowsSandbox/setupStart`：为 `elevated` 或 `unelevated` 模式启动 Windows 沙盒设置；请求会快速返回，并在稍后发出 `windowsSandbox/setupCompleted`。
- `feedback/upload`：提交反馈报告，包括分类、可选的原因说明和日志、对话 ID，以及可选的 `extraLogFiles` 附件。
- `config/read`：解析配置层级后，获取磁盘上的有效配置。
- `externalAgentConfig/detect`：使用 `includeHome` 和可选的 `cwds` 检测可迁移的外部智能体产物；检测到的每一项都包含 `cwd`（主目录对应 `null`）。
- `externalAgentConfig/import`：通过显式传入 `migrationItems` 并指定 `cwd`（主目录使用 `null`），应用所选的外部智能体迁移项。支持的项类型包括配置、技能、`AGENTS.md`、插件、MCP 服务器配置、子智能体、钩子、命令和会话；非空导入会随着相关工作完成而发出 `externalAgentConfig/import/progress` 和 `externalAgentConfig/import/completed`。插件和会话导入可以异步完成。
- `config/value/write`：将单个配置键值对写入磁盘上的用户 `config.toml` 文件。
- `config/batchWrite`：以原子方式将配置更改应用到磁盘上的用户 `config.toml` 文件。
- `configRequirements/read`：从 `requirements.toml` 和/或 MDM 获取要求，包括确切的托管配置、允许列表、固定的 `featureRequirements` 和网络要求；如果您尚未设置任何要求，则返回 `null`。
- `fs/readFile`、`fs/writeFile`、`fs/createDirectory`、`fs/getMetadata`、`fs/readDirectory`、`fs/remove`、`fs/copy`、`fs/watch`、`fs/unwatch` 和 `fs/changed`（通知）：通过 app-server v2 文件系统 API 对文件系统绝对路径执行操作。

插件摘要包含一个 `source` 联合类型。本地插件返回
`{ "type": "local", "path": ... }`，基于 Git 的市场条目返回
`{ "type": "git", "url": ..., "path": ..., "refName": ..., "sha": ... }`，
软件包注册表条目返回
`{ "type": "npm", "package": ..., "version": ..., "registry": ... }`，
远程目录条目返回 `{ "type": "remote" }`。对于仅存在于远程的目录条目，
`PluginMarketplaceEntry.path` 可以为 `null`；请传入
`remoteMarketplaceName` 而非 `marketplacePath` 来读取或安装
这些插件。

## 模型

### 列出模型（`model/list`）

在渲染模型或个性选择器之前，请调用 `model/list` 获取可用模型及其能力。

```json
{ "method": "model/list", "id": 6, "params": { "limit": 20, "includeHidden": false } }
{ "id": 6, "result": {
  "data": [{
    "id": "gpt-5.6-sol",
    "model": "gpt-5.6-sol",
    "displayName": "GPT-5.6-Sol",
    "hidden": false,
    "defaultReasoningEffort": "low",
    "supportedReasoningEfforts": [{
      "reasoningEffort": "low",
      "description": "Fast responses with lighter reasoning"
    }],
    "inputModalities": ["text", "image"],
    "supportsPersonality": true,
    "isDefault": true
  }],
  "nextCursor": null
} }
```

每个模型条目可以包含：

- `supportedReasoningEfforts`：模型支持的推理强度选项。
- `defaultReasoningEffort`：建议客户端使用的默认推理强度。
- `upgrade`：可选的推荐升级目标模型 ID，用于客户端中的迁移提示。
- `upgradeInfo`：可选的升级元数据，用于客户端中的迁移提示。
- `hidden`：模型是否在默认选择器列表中隐藏。
- `inputModalities`：模型支持的输入类型，例如 `text` 和 `image`。
- `supportsPersonality`：模型是否支持 `/personality` 等个性相关指令。
- `isDefault`：模型是否为推荐的默认模型。

默认情况下，`model/list` 仅返回选择器中可见的模型。如果您需要完整列表，并希望在客户端使用 `hidden` 进行筛选，请设置 `includeHidden: true`。

当 `inputModalities` 缺失时（旧版模型目录中会出现这种情况），为保持向后兼容，请将其视为 `["text", "image"]`。

### 列出实验性功能（`experimentalFeature/list`）

使用此端点查询功能标志及其元数据和生命周期阶段：

```json
{ "method": "experimentalFeature/list", "id": 7, "params": { "limit": 20 } }
{ "id": 7, "result": {
  "data": [{
    "name": "unified_exec",
    "stage": "beta",
    "displayName": "Unified exec",
    "description": "Use the unified PTY-backed execution tool.",
    "announcement": "Beta rollout for improved command execution reliability.",
    "enabled": false,
    "defaultEnabled": false
  }],
  "nextCursor": null
} }
```

`stage` 可以是 `beta`、`underDevelopment`、`stable`、`deprecated` 或 `removed`。对于非 Beta 阶段的功能标志，`displayName`、`description` 和 `announcement` 可能为 `null`。

### 检查执行环境（实验性）

在已配置的远程环境中开始工作前，请使用 `environment/info` 检查该环境。
此方法要求 `capabilities.experimentalApi = true`。

```json
{ "method": "environment/info", "id": 8, "params": { "environmentId": "devbox" } }
{ "id": 8, "result": {
  "shell": { "name": "zsh", "path": "/bin/zsh" },
  "cwd": "file:///workspace/project"
} }
```

`cwd` 可以为 `null`。有值时，它是一个规范的 `file:` URI，
使用该环境的原生路径语法。未知环境 ID、连接失败或
协议故障都会返回请求错误。

## 线程

- `thread/read` 读取已存储的线程，但不订阅该线程；设置 `includeTurns` 可在结果中包含轮次。
- `thread/turns/list` 是实验性方法，可分页读取已存储线程的轮次历史，
  而无需恢复该线程。使用 `itemsView` 选择省略轮次项、
  加载其摘要或完整加载这些项。
- `thread/items/list` 是实验性方法，可分页读取已持久化的线程项，并可选择将结果限制为单个轮次。
- `thread/list` 支持游标分页，并可使用 `modelProviders`、`sourceKinds`、`archived`、`isPinned`、`cwd`、`useStateDbOnly`、`searchTerm`，以及实验性的 `parentThreadId` 或 `ancestorThreadId` 进行筛选。
- `thread/loaded/list` 返回当前位于内存中的线程 ID。
- `thread/archive` 将线程的持久化 JSONL 日志移至归档目录，并尝试归档由其创建且尚未归档的后代线程的日志。
- `thread/delete` 永久删除已持久化的活动线程或归档线程，以及由其创建的后代线程。
- `thread/metadata/update` 对已存储的线程元数据进行部分更新，包括已持久化的 `gitInfo` 和 `isPinned`。
- `thread/unsubscribe` 取消当前连接对已加载线程的订阅，并可能在闲置宽限期结束后触发 `thread/closed`。
- `thread/unarchive` 将已归档的线程运行记录恢复到活动会话目录中。
- `thread/compact/start` 触发压缩并立即返回 `{}`。
- `thread/rollback` 已弃用。它会从内存上下文中移除最后 N 个轮次，并在线程的持久化 JSONL 日志中记录回滚标记。
- `thread/inject_items` 将原始 Responses API 项追加到已加载线程中模型可见的历史记录，而不启动用户轮次。

### 启动或恢复线程

当您需要新的 Codex 对话时，请启动一个新线程。

```json
{ "method": "thread/start", "id": 10, "params": {
  "model": "gpt-5.6-terra",
  "cwd": "/Users/me/project",
  "approvalPolicy": "never",
  "sandbox": "workspaceWrite",
  "personality": "friendly",
  "serviceName": "my_app_server_client"
} }
{ "id": 10, "result": {
  "thread": {
    "id": "thr_123",
    "sessionId": "thr_123",
    "preview": "",
    "ephemeral": false,
    "modelProvider": "openai",
    "createdAt": 1730910000
  }
} }
{ "method": "thread/started", "params": { "thread": { "id": "thr_123" } } }
```

`serviceName` 为可选字段。如果您希望 app-server 用您所集成服务的名称标记线程级指标，请设置该字段。

`thread/start`、`thread/resume` 和 `thread/fork` 返回
`instructionSources`，即已加载指令文件的路径数组。
每条路径都使用其来源环境的原生绝对路径语法，
远程环境也不例外。

实验性客户端可在 `thread/start` 中将 `historyMode` 设置为 `"legacy"`
（默认值）或 `"paginated"`。目前尚不支持创建分页线程，
此类请求会返回 JSON-RPC 错误 `-32601`。App-server 可以列出并读取
现有分页记录的摘要，但在支持分页历史记录之前，完整历史记录读取、轮次分页和恢复操作
都会失败并拒绝继续执行。

已选择启用 `capabilities.experimentalApi` 的 Beta 客户端可以传入
具名权限配置方案 ID 作为 `permissions` 的值，而不使用旧版 `sandbox` 字段。
请勿同时发送 `permissions` 和 `sandbox`。请使用
`permissionProfile/list` 并提供项目的 `cwd`，以查询可用的配置方案，
以及托管要求是否允许使用各个配置方案。

`thread.sessionId` 标识当前活动会话树的根节点。根线程
使用自身的线程 ID 作为会话 ID；派生线程则保留
其来源根线程的会话 ID。客户端应从
`thread.sessionId` 读取会话 ID，而不是根据线程 ID 推导。

要继续已存储的会话，请调用 `thread/resume`，并传入您之前记录的 `thread.id`。响应结构与 `thread/start` 相同。您还可以传入 `thread/start` 支持的相同配置覆盖项，例如 `personality`：

```json
{ "method": "thread/resume", "id": 11, "params": {
  "threadId": "thr_123",
  "personality": "friendly"
} }
{ "id": 11, "result": { "thread": { "id": "thr_123", "name": "Bug bash notes", "ephemeral": false } } }
```

仅恢复线程不会更新 `thread.updatedAt`，也不会更新运行记录文件的修改时间。时间戳会在您启动轮次时更新。

如果您在配置中将已启用的 MCP 服务器标记为 `required`，而该服务器初始化失败，则 `thread/start` 和 `thread/resume` 会失败，而不会在缺少该服务器的情况下继续执行。

`dynamicTools` 是 `thread/start` 中的实验性字段（需要 `capabilities.experimentalApi = true`）。Codex 会将这些动态工具持久化到线程运行记录的元数据中，并在您未提供新的动态工具时，通过 `thread/resume` 恢复它们。

如果您恢复线程时使用的模型与运行记录中记载的模型不同，Codex 会发出警告，并在下一轮应用一次性模型切换指令。

### 管理线程目标

使用 `thread/goal/set`、`thread/goal/get` 和 `thread/goal/clear` 可管理持久化的目标状态；
TUI 中的 `/goal` 呈现的也是同一状态。

```json
{ "method": "thread/goal/set", "id": 13, "params": {
  "threadId": "thr_123",
  "objective": "Finish the migration and keep tests green",
  "status": "active",
  "tokenBudget": 40000
} }
{ "id": 13, "result": { "goal": {
  "threadId": "thr_123",
  "objective": "Finish the migration and keep tests green",
  "status": "active",
  "tokenBudget": 40000,
  "tokensUsed": 0,
  "timeUsedSeconds": 0
} } }
{ "method": "thread/goal/updated", "params": {
  "threadId": "thr_123",
  "goal": {
    "threadId": "thr_123",
    "objective": "Finish the migration and keep tests green",
    "status": "active",
    "tokenBudget": 40000,
    "tokensUsed": 0,
    "timeUsedSeconds": 0
  }
} }
```

目标内容不得为空，且最多为 4,000 个字符。提供新的目标内容
会替换原目标并重置用量统计。提供当前非终态目标的内容，
或省略 `objective`，会更新状态或 Token 预算，
同时保留用量历史记录。

要从已存储的会话创建分支，请调用 `thread/fork` 并传入 `thread.id`。这会创建一个新的线程 ID，并为其发出 `thread/started` 通知。传入
`lastTurnId` 可复制截至该轮次（包含该轮次）的历史记录，
不包含之后的轮次：

```json
{ "method": "thread/fork", "id": 12, "params": { "threadId": "thr_123", "lastTurnId": "turn_456" } }
{ "id": 12, "result": { "thread": { "id": "thr_456", "sessionId": "thr_123", "forkedFromId": "thr_123" } } }
{ "method": "thread/started", "params": { "thread": { "id": "thr_456" } } }
```

App-server 会拒绝指向进行中轮次的 `lastTurnId`。如果您在
源线程的轮次尚未结束时省略该字段，派生线程会记录中断标记，
而不会保留未标记的不完整轮次。

传入 `ephemeral: true` 可在内存中创建派生线程，
且不会将其加入已存储的线程列表：

```json
{
  "method": "thread/fork",
  "id": 13,
  "params": {
    "threadId": "thr_123",
    "ephemeral": true
  }
}
{
  "id": 13,
  "result": {
    "thread": {
      "id": "thr_789",
      "sessionId": "thr_789",
      "forkedFromId": "thr_123",
      "ephemeral": true
    }
  }
}
```

为分页线程创建临时派生线程时，还需要 `excludeTurns: true`。
该字段是实验性字段，需要 `capabilities.experimentalApi = true`。

设置用户可见的线程标题后，app-server 会在 `thread/list`、`thread/read`、`thread/resume`、`thread/unarchive` 和 `thread/rollback` 的响应中填充 `thread.name`。在设置标题之前，`thread/start` 和 `thread/fork` 可能会省略 `name`（或返回 `null`）。

### 读取已存储的线程（不恢复）

如需获取已存储的线程数据，但不想恢复线程或订阅其事件，请使用 `thread/read`。

- `includeTurns`：设为 `true` 时，响应包含线程的轮次；设为 `false` 或省略时，仅返回线程摘要。
- 返回的 `thread` 对象包含运行时 `status`，其取值为 `notLoaded`、`idle`、`systemError` 或附带 `activeFlags` 的 `active`。

```json
{ "method": "thread/read", "id": 19, "params": { "threadId": "thr_123", "includeTurns": true } }
{ "id": 19, "result": { "thread": { "id": "thr_123", "name": "Bug bash notes", "ephemeral": false, "status": { "type": "notLoaded" }, "turns": [] } } }
```

与 `thread/resume` 不同，`thread/read` 不会将线程加载到内存中，也不会发出 `thread/started`。

### 列出线程轮次

`thread/turns/list` 是实验性接口。它可在不恢复线程的情况下，分页读取已存储线程的轮次历史。结果默认按从新到旧排序，因此客户端可通过 `nextCursor` 获取更早的轮次。响应还包含 `backwardsCursor`；将其作为 `cursor` 并搭配 `sortDirection: "asc"` 传入，即可获取比先前那一页中首项更新的轮次。

`itemsView` 控制响应中轮次项数据的详细程度：

- `notLoaded` 不返回项。
- `summary` 返回项的摘要数据；省略该字段时，默认使用此值。
- `full` 返回完整的项数据。

```json
{ "method": "thread/turns/list", "id": 20, "params": {
  "threadId": "thr_123",
  "limit": 50,
  "sortDirection": "desc",
  "itemsView": "summary"
} }
{ "id": 20, "result": {
  "data": [],
  "nextCursor": "older-turns-cursor-or-null",
  "backwardsCursor": "newer-turns-cursor-or-null"
} }
```

`thread/items/list` 也是实验性接口。它可在不恢复线程的情况下，
分页读取持久化的项。传入 `turnId` 可将结果限制为单个轮次，
省略则可分页读取整个线程中的项。当前使用的线程存储必须支持项分页；
否则，服务器会返回不支持该方法的错误。

### 列出线程（支持分页和筛选）

`thread/list` 可用于呈现历史记录界面。结果默认按 `createdAt` 从新到旧排列。筛选条件在分页前生效。您可以传入以下参数的任意组合：

- `cursor`：来自先前响应的不透明字符串；获取第一页时请省略。
- `limit`：未设置时，服务器会采用合理的默认页大小。
- `sortKey`：`created_at`（默认）、`updated_at` 或 `recency_at`。
- `sortDirection`：`desc`（默认）或 `asc`。
- `modelProviders`：将结果限制为特定提供商；未设置、设为 null 或使用空数组时会包含所有提供商。
- `sourceKinds`：将结果限制为特定线程来源。省略或设为 `[]` 时，服务器默认仅包含交互式来源：`cli` 和 `vscode`。
- `archived`：设为 `true` 时，仅列出已归档线程。设为 `false` 或省略时，列出未归档线程（默认）。
- `isPinned`：提供该参数时，仅返回持久化置顶状态与其匹配的线程。省略时同时返回已置顶和未置顶的线程。
- `cwd`：仅返回会话当前工作目录与该路径或数组中某一路径完全匹配的线程。相对路径以 app-server 进程的工作目录为基准解析。
- `useStateDbOnly`：设为 `true` 时，返回状态数据库中的结果，不扫描 JSONL 线程日志来修复元数据。省略或传入 `false` 时，使用默认的扫描并修复行为。
- `searchTerm`：仅返回提取出的标题包含此文本片段的线程，匹配区分大小写。
- `parentThreadId`：仅返回指定父线程的直接子线程。此筛选条件是实验性的，需要 `capabilities.experimentalApi = true`。
- `ancestorThreadId`：仅返回指定线程生成的后代线程，不限层级。此筛选条件是实验性的，需要 `capabilities.experimentalApi = true`；请勿与 `parentThreadId` 组合使用。

`sourceKinds` 接受以下值：

- `cli`
- `vscode`
- `exec`
- `appServer`
- `subAgent`
- `subAgentReview`
- `subAgentCompact`
- `subAgentThreadSpawn`
- `subAgentOther`
- `unknown`

示例：

```json
{ "method": "thread/list", "id": 20, "params": {
  "cursor": null,
  "limit": 25,
  "sortKey": "created_at"
} }
{ "id": 20, "result": {
  "data": [
    { "id": "thr_a", "preview": "Create a TUI", "ephemeral": false, "isPinned": true, "modelProvider": "openai", "createdAt": 1730831111, "updatedAt": 1730831111, "name": "TUI prototype", "status": { "type": "notLoaded" } },
    { "id": "thr_b", "preview": "Fix tests", "ephemeral": false, "isPinned": false, "modelProvider": "openai", "createdAt": 1730750000, "updatedAt": 1730750000, "status": { "type": "notLoaded" } }
  ],
  "nextCursor": "opaque-token-or-null"
} }
```

当 `nextCursor` 为 `null` 时，即表示已到最后一页。

### 更新已存储的线程元数据

使用 `thread/metadata/update` 可在不恢复线程的情况下，
局部更新已存储的线程元数据。设置 `isPinned` 可置顶或取消置顶线程，或更新 `gitInfo` 来修改
持久化的 Git 元数据。省略的字段保持不变；显式传入 `null` 会清除
已存储的 Git 元数据值。

```json
{ "method": "thread/metadata/update", "id": 21, "params": {
  "threadId": "thr_123",
  "isPinned": true,
  "gitInfo": { "branch": "feature/sidebar-pr" }
} }
{ "id": 21, "result": {
  "thread": {
    "id": "thr_123",
    "isPinned": true,
    "gitInfo": { "sha": null, "branch": "feature/sidebar-pr", "originUrl": null }
  }
} }
```

### 跟踪线程状态变化

每当已加载线程的运行时状态发生变化时，都会发出 `thread/status/changed`。载荷包含 `threadId` 和新的 `status`。

```json
{
  "method": "thread/status/changed",
  "params": {
    "threadId": "thr_123",
    "status": { "type": "active", "activeFlags": ["waitingOnApproval"] }
  }
}
```

### 列出已加载的线程

`thread/loaded/list` 返回当前已加载到内存中的线程 ID。

```json
{ "method": "thread/loaded/list", "id": 21 }
{ "id": 21, "result": { "data": ["thr_123", "thr_456"] } }
```

### 取消订阅已加载的线程

`thread/unsubscribe` 会取消当前连接对线程的订阅。响应状态为以下值之一：

- `unsubscribed`：连接此前订阅了该线程，现在已取消订阅。
- `notSubscribed`：连接此前未订阅该线程。
- `notLoaded`：线程未加载。

如果这是最后一个订阅者，服务器会保持线程的加载状态，直到线程连续 30 分钟既无订阅者也无活动。宽限期结束后，app-server 会卸载线程，并发出 `thread/status/changed` 通知（状态变为 `notLoaded`）以及 `thread/closed`。

```json
{ "method": "thread/unsubscribe", "id": 22, "params": { "threadId": "thr_123" } }
{ "id": 22, "result": { "status": "unsubscribed" } }
```

如果该线程之后过期：

```json
{ "method": "thread/status/changed", "params": {
    "threadId": "thr_123",
    "status": { "type": "notLoaded" }
} }
{ "method": "thread/closed", "params": { "threadId": "thr_123" } }
```

### 归档线程

使用 `thread/archive` 可将持久化的线程日志（在磁盘上存储为 JSONL 文件）移入已归档会话目录。归档线程时，还会尝试归档由其生成且尚未归档的后代线程。

```json
{ "method": "thread/archive", "id": 22, "params": { "threadId": "thr_b" } }
{ "id": 22, "result": {} }
{ "method": "thread/archived", "params": { "threadId": "thr_b" } }
{ "method": "thread/archived", "params": { "threadId": "thr_child" } }
```

已归档线程不会出现在之后对 `thread/list` 的调用结果中，除非您传入 `archived: true`。服务器会为实际归档的每个线程发出一条 `thread/archived` 通知；若有生成的后代线程无法归档，请求仍可能成功，但不会为该后代线程发出归档通知。

### 删除线程

使用 `thread/delete` 可永久删除已持久化的活动线程或已归档线程
及其生成的后代线程。服务器会先移除现有的运行记录文件和
相关元数据，再返回成功；缺失的运行记录文件会被视为
已经删除。无法删除临时根线程。

```json
{ "method": "thread/delete", "id": 23, "params": { "threadId": "thr_b" } }
{ "id": 23, "result": {} }
{ "method": "thread/deleted", "params": { "threadId": "thr_b" } }
{ "method": "thread/deleted", "params": { "threadId": "thr_child" } }
```

### 取消线程归档

使用 `thread/unarchive` 可将已归档线程的运行记录移回活动会话目录。

```json
{ "method": "thread/unarchive", "id": 24, "params": { "threadId": "thr_b" } }
{ "id": 24, "result": { "thread": { "id": "thr_b", "name": "Bug bash notes" } } }
{ "method": "thread/unarchived", "params": { "threadId": "thr_b" } }
```

### 触发线程压缩

使用 `thread/compact/start` 可手动触发线程历史记录压缩。请求会立即返回 `{}`。

App-server 会针对同一 `threadId`，通过标准的 `turn/*` 和 `item/*` 通知报告进度，其中包含 `contextCompaction` 项的生命周期（先 `item/started`，后 `item/completed`）。

```json
{ "method": "thread/compact/start", "id": 25, "params": { "threadId": "thr_b" } }
{ "id": 25, "result": {} }
```

### 运行线程的 Shell 命令

对于用户发起且属于某个线程的 shell 命令，请使用 `thread/shellCommand`。请求会立即返回 `{}`，同时通过标准的 `turn/*` 和 `item/*` 通知流式传输进度。

此 API 在沙盒外运行，拥有完全访问权限，且不会继承线程的沙盒策略。客户端只应针对由用户明确发起的命令开放此 API。

如果线程已有正在进行的轮次，该命令会作为该轮次的辅助操作运行，其格式化输出会注入该轮次的消息流。如果线程处于空闲状态，app-server 会为该 shell 命令启动独立轮次。

设置 `timeoutMs` 可限制执行时间，单位为毫秒。
省略此字段或传入 `null` 时，会使用一小时的默认值。`0` 表示请求立即超时；负值会被拒绝。
RPC 确认仍会立即返回，不受该超时设置影响。

```json
{ "method": "thread/shellCommand", "id": 26, "params": { "threadId": "thr_b", "command": "git status --short", "timeoutMs": 10000 } }
{ "id": 26, "result": {} }
```

### 清理后台终端

使用 `thread/backgroundTerminals/clean` 可停止与线程关联的所有正在运行的后台终端。此方法处于实验阶段，需要 `capabilities.experimentalApi = true`。

```json
{ "method": "thread/backgroundTerminals/clean", "id": 27, "params": { "threadId": "thr_b" } }
{ "id": 27, "result": {} }
```

使用 `thread/backgroundTerminals/list` 可查看已加载线程中正在运行的后台终端。
请求支持基于 `cursor` 和 `limit` 的标准分页，
返回的 `processId` 是 app-server 进程 ID。
此方法处于实验阶段，需要 `capabilities.experimentalApi = true`：

```json
{ "method": "thread/backgroundTerminals/list", "id": 28, "params": { "threadId": "thr_b" } }
{ "id": 28, "result": { "data": [
  {
    "itemId": "item_456",
    "processId": "42",
    "command": "python3 -m http.server",
    "cwd": "/workspace",
    "osPid": null,
    "cpuPercent": null,
    "rssKb": null
  }
], "nextCursor": null } }
```

使用 `thread/backgroundTerminals/terminate` 并传入该 `processId`，即可停止一个后台终端。
此方法处于实验阶段，
需要 `capabilities.experimentalApi = true`：

```json
{ "method": "thread/backgroundTerminals/terminate", "id": 29, "params": { "threadId": "thr_b", "processId": "42" } }
{ "id": 29, "result": { "terminated": true } }
```

### 回滚最近的轮次

`thread/rollback` 已弃用，并将被移除。
它会从内存上下文中移除最后 `numTurns` 个条目，
并将回滚标记持久保存到运行日志中。
返回的 `thread` 包含回滚后填充的 `turns`。

```json
{ "method": "thread/rollback", "id": 30, "params": { "threadId": "thr_b", "numTurns": 1 } }
{ "id": 30, "result": { "thread": { "id": "thr_b", "name": "Bug bash notes", "ephemeral": false } } }
```

## 轮次

`input` 字段接受项列表：

- `{ "type": "text", "text": "Explain this diff" }`
- `{ "type": "image", "url": "https://.../design.png" }`
- `{ "type": "localImage", "path": "/tmp/screenshot.png" }`

您可以按轮次覆盖配置设置（模型、推理强度、个性、`cwd`、沙盒策略和摘要）。指定后，这些设置会成为同一线程后续轮次的默认值。`outputSchema` 仅适用于当前轮次。对于 `sandboxPolicy.type = "externalSandbox"`，请将 `networkAccess` 设为 `restricted` 或 `enabled`；对于 `workspaceWrite`，`networkAccess` 仍为布尔值。

对于 `turn/start.collaborationMode`，`settings.developer_instructions: null` 表示“使用所选模式的内置指令”，而不是清除模式指令。

### 沙盒读取权限（`ReadOnlyAccess`）

`sandboxPolicy` 支持显式读取权限控制：

- `readOnly`：`access` 可选（默认为 `{ "type": "fullAccess" }`，也可限定可访问的根目录）。
- `workspaceWrite`：`readOnlyAccess` 可选（默认为 `{ "type": "fullAccess" }`，也可限定可访问的根目录）。

受限读取权限的结构：

```json
{
  "type": "restricted",
  "includePlatformDefaults": true,
  "readableRoots": ["/Users/me/shared-read-only"]
}
```

在 macOS 上，`includePlatformDefaults: true` 会为读取受限的会话追加经过筛选的平台默认 Seatbelt 策略。这样可以提高工具兼容性，同时不会全面开放对整个 `/System` 的访问。

示例：

```json
{ "type": "readOnly", "access": { "type": "fullAccess" } }
```

```json
{
  "type": "workspaceWrite",
  "writableRoots": ["/Users/me/project"],
  "readOnlyAccess": {
    "type": "restricted",
    "includePlatformDefaults": true,
    "readableRoots": ["/Users/me/shared-read-only"]
  },
  "networkAccess": false
}
```

### 启动轮次

```json
{ "method": "turn/start", "id": 30, "params": {
  "threadId": "thr_123",
  "input": [ { "type": "text", "text": "Run tests" } ],
  "cwd": "/Users/me/project",
  "approvalPolicy": "unlessTrusted",
  "sandboxPolicy": {
    "type": "workspaceWrite",
    "writableRoots": ["/Users/me/project"],
    "networkAccess": true
  },
  "model": "gpt-5.6-terra",
  "effort": "medium",
  "summary": "concise",
  "personality": "friendly",
  "outputSchema": {
    "type": "object",
    "properties": { "answer": { "type": "string" } },
    "required": ["answer"],
    "additionalProperties": false
  }
} }
{ "id": 30, "result": { "turn": { "id": "turn_456", "status": "inProgress", "items": [], "error": null } } }
```

若要使用客户端所运行工具的输出来启动轮次，请传入 `toolOutput`，
其中包含非空的 `name`、可选的 `namespace`，以及值为字符串或内容项数组的 `output`。
请将 `input` 设为空数组；
不能将 `toolOutput` 与非空的用户输入一起使用。

```json
{
  "method": "turn/start",
  "id": 31,
  "params": {
    "threadId": "thr_123",
    "input": [],
    "toolOutput": {
      "name": "run_tests",
      "namespace": null,
      "output": "All 42 tests passed."
    }
  }
}
```

该输出在对话中仍属于工具输出，
并在通知和持久化历史记录中以 `functionCallOutput` 项的形式出现。
如果已有正在进行的常规轮次，Codex 会将该输出加入该轮次的队列。

### 向线程注入项

使用 `thread/inject_items` 可将预先构建的 Responses API 项追加到已加载线程的提示历史记录中，而无需启动用户轮次。这些项会持久保存到运行记录中，并包含在后续模型请求中。

```json
{ "method": "thread/inject_items", "id": 31, "params": {
  "threadId": "thr_123",
  "items": [
    {
      "type": "message",
      "role": "assistant",
      "content": [{ "type": "output_text", "text": "Previously computed context." }]
    }
  ]
} }
{ "id": 31, "result": {} }
```

### 引导正在进行的轮次

使用 `turn/steer` 可向当前正在进行的轮次追加更多用户输入。

- 请包含 `expectedTurnId`，其值必须与正在进行的轮次 ID 一致。
- 如果线程中没有正在进行的轮次，请求将失败。
- `turn/steer` 不会发出新的 `turn/started` 通知。
- `turn/steer` 不接受轮次级配置覆盖（`model`、`cwd`、`sandboxPolicy` 或 `outputSchema`）。

```json
{ "method": "turn/steer", "id": 32, "params": {
  "threadId": "thr_123",
  "input": [ { "type": "text", "text": "Actually focus on failing tests first." } ],
  "expectedTurnId": "turn_456"
} }
{ "id": 32, "result": { "turnId": "turn_456" } }
```

### 启动轮次（调用技能）

在文本输入中包含 `$<skill-name>`，并同时添加一个 `skill` 输入项，即可显式调用技能。

```json
{ "method": "turn/start", "id": 33, "params": {
  "threadId": "thr_123",
  "input": [
    { "type": "text", "text": "$skill-creator Add a new skill for triaging flaky CI and include step-by-step usage." },
    { "type": "skill", "name": "skill-creator", "path": "/Users/me/.codex/skills/skill-creator/SKILL.md" }
  ]
} }
{ "id": 33, "result": { "turn": { "id": "turn_457", "status": "inProgress", "items": [], "error": null } } }
```

### 中断轮次

```json
{ "method": "turn/interrupt", "id": 31, "params": { "threadId": "thr_123", "turnId": "turn_456" } }
{ "id": 31, "result": {} }
```

成功后，该轮次会以 `status: "interrupted"` 结束。

## 审查

`review/start` 会为线程运行 Codex 审查器，并流式传输审查项。审查目标包括：

- `uncommittedChanges`
- `baseBranch`（与某个分支比较差异）
- `commit`（审查特定提交）
- `custom`（自由格式指令）

使用 `delivery: "inline"`（默认值）可在现有线程中运行审查，使用 `delivery: "detached"` 则会派生新的审查线程。

请求/响应示例：

```json
{ "method": "review/start", "id": 40, "params": {
  "threadId": "thr_123",
  "delivery": "inline",
  "target": { "type": "commit", "sha": "1234567deadbeef", "title": "Polish tui colors" }
} }
{ "id": 40, "result": {
  "turn": {
    "id": "turn_900",
    "status": "inProgress",
    "items": [
      { "type": "userMessage", "id": "turn_900", "content": [ { "type": "text", "text": "Review commit 1234567: Polish tui colors" } ] }
    ],
    "error": null
  },
  "reviewThreadId": "thr_123"
} }
```

若要在独立线程中审查，请使用 `"delivery": "detached"`。响应结构保持不变，但 `reviewThreadId` 将是新审查线程的 ID（不同于原始 `threadId`）。在流式传输审查轮次之前，服务器还会为新线程发出 `thread/started` 通知。

Codex 会先按常规流式发送 `turn/started` 通知，随后发送 `item/started`，其中包含 `enteredReviewMode` 项：

```json
{
  "method": "item/started",
  "params": {
    "item": {
      "type": "enteredReviewMode",
      "id": "turn_900",
      "review": "current changes"
    }
  }
}
```

审查器完成后，服务器会发出 `item/started` 和 `item/completed`，其中包含带有最终审查文本的 `exitedReviewMode` 项：

```json
{
  "method": "item/completed",
  "params": {
    "item": {
      "type": "exitedReviewMode",
      "id": "turn_900",
      "review": "Looks solid overall..."
    }
  }
}
```

请使用此通知在您的客户端中呈现审查器输出。

## 进程执行

`process/*` 是用于显式控制进程的实验性 API。
它要求 `capabilities.experimentalApi = true`，并在 Codex 沙盒外运行。
仅当您的客户端有意开放不受沙盒限制的本地进程控制时，
才应使用它。

使用 `process/spawn` 启动进程并提供 `processHandle`，
然后使用该句柄发送 stdin、调整大小和终止请求。
输出通过 `process/outputDelta` 通知流式传输，
完成状态则通过 `process/exited` 流式传输。

```json
{ "method": "process/spawn", "id": 48, "params": {
  "command": ["python3", "-m", "pytest", "-q"],
  "processHandle": "pytest-1",
  "cwd": "/Users/me/project",
  "tty": true
} }
{ "id": 48, "result": {} }
{ "method": "process/outputDelta", "params": {
  "processHandle": "pytest-1",
  "stream": "stdout",
  "deltaBase64": "Li4u"
} }
{ "method": "process/exited", "params": {
  "processHandle": "pytest-1",
  "exitCode": 0
} }
```

使用 `process/writeStdin` 并传入 `deltaBase64`、`closeStdin` 或两者，
即可发送输入。使用 `process/resizePty` 处理 PTY 大小调整事件，
使用 `process/kill` 终止正在运行的进程。

## 命令执行

`command/exec` 会在服务器沙盒中运行单个命令（`argv` 数组），且不创建线程。

```json
{ "method": "command/exec", "id": 50, "params": {
  "command": ["ls", "-la"],
  "cwd": "/Users/me/project",
  "sandboxPolicy": { "type": "workspaceWrite" },
  "timeoutMs": 10000
} }
{ "id": 50, "result": { "exitCode": 0, "stdout": "...", "stderr": "" } }
```

如果您已将服务器进程置于沙盒中，并希望 Codex 跳过自身的沙盒隔离，请使用 `sandboxPolicy.type = "externalSandbox"`。对于外部沙盒模式，请将 `networkAccess` 设为 `restricted`（默认值）或 `enabled`。对于 `readOnly` 和 `workspaceWrite`，请使用上文所示的相同可选 `access` / `readOnlyAccess` 结构。

注意事项：

- 服务器会拒绝空的 `command` 数组。
- `sandboxPolicy` 接受与 `turn/start` 相同的结构（例如 `dangerFullAccess`、`readOnly`、`workspaceWrite`、`externalSandbox`）。
- 省略时，`timeoutMs` 会采用服务器默认值。
- 对于基于 PTY 的会话，请设置 `tty: true`；如果您计划随后调用 `command/exec/write`、`command/exec/resize` 或 `command/exec/terminate`，请使用 `processId`。
- 设置 `streamStdoutStderr: true`，即可在命令运行期间接收 `command/exec/outputDelta` 通知。

### 读取管理员要求（`configRequirements/read`）

使用 `configRequirements/read` 可查看从 `requirements.toml` 和/或 MDM 加载并实际生效的管理员要求。

```json
{ "method": "configRequirements/read", "id": 52, "params": {} }
{ "id": 52, "result": {
  "requirements": {
    "allowedApprovalPolicies": ["onRequest", "unlessTrusted"],
    "allowedSandboxModes": ["readOnly", "workspaceWrite"],
    "featureRequirements": {
      "personality": true,
      "unified_exec": false
    },
    "network": {
      "enabled": true,
      "allowedDomains": ["api.openai.com"],
      "allowUnixSockets": ["/tmp/example.sock"],
      "dangerouslyAllowAllUnixSockets": false
    }
  }
} }
```

未配置任何要求时，`result.requirements` 为 `null`。有关受支持的键和值的详细信息，请参阅 [`requirements.toml`](/zh-Hans/codex/config-file/config-reference#requirementstoml) 文档。

### Windows 沙盒设置（`windowsSandbox/setupStart`）

自定义 Windows 客户端可以异步触发沙盒设置，无需阻塞等待启动检查。

```json
{ "method": "windowsSandbox/setupStart", "id": 53, "params": { "mode": "elevated" } }
{ "id": 53, "result": { "started": true } }
```

App-server 会在后台启动设置流程，并在稍后发出完成通知：

```json
{
  "method": "windowsSandbox/setupCompleted",
  "params": { "mode": "elevated", "success": true, "error": null }
}
```

模式：

- `elevated`：运行需要提升权限的 Windows 沙盒设置流程。
- `unelevated`：运行旧版设置/预检流程。

## 文件系统

v2 文件系统 API 使用绝对路径进行操作。当客户端需要在文件或目录更改后将 UI 状态标记为失效时，请使用 `fs/watch`。

```json
{ "method": "fs/watch", "id": 54, "params": {
  "watchId": "0195ec6b-1d6f-7c2e-8c7a-56f2c4a8b9d1",
  "path": "/Users/me/project/.git/HEAD"
} }
{ "id": 54, "result": { "path": "/Users/me/project/.git/HEAD" } }
{ "method": "fs/changed", "params": {
  "watchId": "0195ec6b-1d6f-7c2e-8c7a-56f2c4a8b9d1",
  "changedPaths": ["/Users/me/project/.git/HEAD"]
} }
{ "method": "fs/unwatch", "id": 55, "params": {
  "watchId": "0195ec6b-1d6f-7c2e-8c7a-56f2c4a8b9d1"
} }
{ "id": 55, "result": {} }
```

监视文件时，会针对该文件路径发出 `fs/changed`，包括通过替换或重命名操作产生的更新。

## 事件

事件通知是由服务器发起的事件流，涵盖线程生命周期、轮次生命周期及其中的条目。启动或恢复线程后，请持续从当前使用的传输流中读取 `thread/started`、`thread/archived`、`thread/unarchived`、`thread/closed`、`thread/status/changed`、`turn/*`、`item/*` 和 `serverRequest/resolved` 通知。

### 选择不接收通知

客户端可以针对每个连接，在 `initialize.params.capabilities.optOutNotificationMethods` 中发送确切的方法名称，以屏蔽特定通知。

- 仅支持精确匹配：`item/agentMessage/delta` 只会屏蔽该方法的通知。
- 未知的方法名称会被忽略。
- 适用于当前的 `thread/*`、`turn/*`、`item/*` 以及相关的 v2 通知。
- 不适用于请求、响应或错误。

### 模糊文件搜索事件（实验性）

模糊文件搜索会话 API 会针对每个查询发出通知：

- `fuzzyFileSearch/sessionUpdated`：`{ sessionId, query, files }`，包含活动查询的当前匹配结果。
- `fuzzyFileSearch/sessionCompleted`：`{ sessionId }`，在该查询的索引构建和匹配完成后发出。

### 警告事件

- `configWarning`：`{ summary, details?, path?, range? }`，用于报告可恢复的
  配置或初始化问题。
- `warning`：`{ threadId?, message }`，用于报告非致命的运行时警告。

### Windows 沙盒设置事件

- `windowsSandbox/setupCompleted`：`{ mode, success, error }`，在 `windowsSandbox/setupStart` 请求完成后发出。

### 轮次事件

- `turn/started`：`{ turn }`，包含轮次 ID、空的 `items` 和 `status: "inProgress"`。
- `turn/completed`：`{ turn }`，其中 `turn.status` 为 `completed`、`interrupted` 或 `failed`；失败时包含 `{ error: { message, codexErrorInfo?, additionalDetails? } }`。
- `turn/diff/updated`：`{ threadId, turnId, diff }`，包含该轮次所有文件更改汇总后的最新统一格式差异。
- `turn/plan/updated`：`{ turnId, explanation?, plan }`，每当智能体展示或更改其计划时发出；每个 `plan` 条目均为 `{ step, status }`，其中 `status` 的取值为 `pending`、`inProgress` 或 `completed`。
- `hook/started` 和 `hook/completed`：`{ threadId, turnId?, run }`，分别在同步生命周期钩子启动时和最终运行摘要可用时发出。异步钩子不会触发这些通知。
- `model/safetyBuffering/updated`：`{ threadId, turnId, model, useCases, reasons, showBufferingUi, fasterModel }`，在响应进入临时安全缓冲状态时发出。
- `model/rerouted`：`{ threadId, turnId, fromModel, toModel, reason }`，在服务将请求路由到另一个模型时发出。
- `model/verification`：`{ threadId, turnId, verifications }`，在服务要求进行额外账户验证时发出。
- `thread/tokenUsage/updated`：活动线程的用量更新。

`turn/diff/updated` 和 `turn/plan/updated` 目前包含空的 `items` 数组，即使条目事件正在流式传输也是如此。请将 `item/*` 通知作为轮次条目的权威数据源。

### 条目

`ThreadItem` 是轮次响应和 `item/*` 通知中携带的带标签联合类型。常见的条目类型包括：

- `userMessage`：`{id, content}`，其中 `content` 是用户输入列表（`text`、`image` 或 `localImage`）。
- `functionCallOutput`：`{id, name, namespace, output}`，用于通过 `turn/start.toolOutput` 提供的独立工具输出。`namespace` 可以为 `null`。
- `agentMessage`：`{id, text, phase?}`，包含累积的智能体回复。`phase` 存在时，采用 Responses API 传输协议中的取值（`commentary`、`final_answer`）。
- `plan`：`{id, text}`，包含在计划模式下拟定的计划文本。请以 `item/completed` 中最终的 `plan` 条目为准。
- `reasoning`：`{id, summary, content}`，其中 `summary` 保存流式传输的推理摘要，`content` 保存原始推理块。
- `commandExecution`：`{id, command, cwd, status, commandActions, aggregatedOutput?, exitCode?, durationMs?}`。
- `fileChange`：`{id, changes, status}`，描述拟进行的编辑；`changes` 列出 `{path, kind, diff}`。
- `mcpToolCall`：`{id, server, tool, status, arguments, appContext?, pluginId?, result?, error?}`。对于受信任的 MCP 应用，`appContext` 可包含 `connectorId`、`linkId`、`resourceUri`、`appName`、`templateId` 和连接器的稳定操作名称 `actionName`。较早持久化的条目可能不包含较新的元数据。请使用 `appContext.resourceUri`，替代已弃用的顶层字段 `mcpAppResourceUri`。
- `dynamicToolCall`：`{id, tool, arguments, status, contentItems?, success?, durationMs?}`，用于由客户端执行的动态工具调用。
- `collabToolCall`：`{id, tool, status, senderThreadId, receiverThreadId?, newThreadId?, prompt?, agentStatus?}`。
- `webSearch`：`{id, query, action?}`，用于智能体发出的网页搜索请求。
- `imageView`：`{id, path}`，在智能体调用图像查看器工具时发出。
- `enteredReviewMode`：`{id, review}`，在审查器开始运行时发送。
- `exitedReviewMode`：`{id, review}`，在审查器完成运行时发出。
- `contextCompaction`：`{id}`，在 Codex 压缩对话历史记录时发出。

对于 `webSearch.action`，操作的 `type` 可以是 `search`（`query?`、`queries?`）、`openPage`（`url?`）或 `findInPage`（`url?`、`pattern?`）。

App Server 已弃用旧版 `thread/compacted` 通知；请改用 `contextCompaction` 条目。

所有条目都会发出以下两个共用的生命周期事件：

- `item/started`：新工作单元开始时发出完整的 `item`；`item.id` 与增量使用的 `itemId` 一致。
- `item/completed`：工作完成后发送最终的 `item`；最终状态应以此为准。

### 条目增量

- `item/agentMessage/delta`：将流式文本追加到智能体消息。
- `item/plan/delta`：以流式方式传输拟定的计划文本。最终的 `plan` 条目可能与拼接后的增量不完全相同。
- `item/reasoning/summaryTextDelta`：以流式方式传输可读的推理摘要；每当开始新的摘要部分时，`summaryIndex` 都会递增。
- `item/reasoning/summaryPartAdded`：标记推理摘要各部分之间的边界。
- `item/reasoning/textDelta`：以流式方式传输原始推理文本（模型支持时）。
- `item/commandExecution/outputDelta`：以流式方式传输命令的 stdout/stderr；请按顺序追加增量内容。
- `item/fileChange/outputDelta`：用于旧版 `apply_patch` 文本输出的兼容性通知，现已弃用。当前 app-server 版本不再发送此通知；请改用 `fileChange` 项和 `turn/diff/updated`。

## 错误

如果轮次失败，服务器会发送包含 `{ error: { message, codexErrorInfo?, additionalDetails? } }` 的 `error` 事件，然后以 `status: "failed"` 结束该轮次。如果有上游 HTTP 状态码，它会出现在 `codexErrorInfo.httpStatusCode` 中。

常见的 `codexErrorInfo` 值包括：

- `ContextWindowExceeded`
- `UsageLimitExceeded`
- `HttpConnectionFailed`（上游 4xx/5xx 错误）
- `ResponseStreamConnectionFailed`
- `ResponseStreamDisconnected`
- `ResponseTooManyFailedAttempts`
- `BadRequest`、`Unauthorized`、`SandboxError`、`InternalServerError`、`Other`

如果有上游 HTTP 状态码，服务器会通过相应 `codexErrorInfo` 变体中的 `httpStatusCode` 转发该状态码。

## 审批

根据用户的 Codex 设置，命令执行和文件更改可能需要审批。app-server 会向客户端发送由服务器发起的 JSON-RPC 请求，客户端则返回包含审批决定的载荷。

- 命令执行的审批决定：`accept`、`acceptForSession`、`decline`、`cancel` 或 `{ "acceptWithExecpolicyAmendment": { "execpolicy_amendment": ["cmd", "..."] } }`。
- 文件更改的审批决定：`accept`、`acceptForSession`、`decline`、`cancel`。

- 请求包含 `threadId` 和 `turnId`；请使用它们将 UI 状态限定在当前对话内。
- 服务器会恢复执行或拒绝执行该操作，并通过 `item/completed` 结束该项。

### 命令执行审批

消息顺序：

1. `item/started` 会显示待处理的 `commandExecution` 项，其中包含 `command`、`cwd` 等字段。
2. `item/commandExecution/requestApproval` 包含 `itemId`、`threadId`、`turnId`，以及可选的 `reason`、`command`、`cwd`、`commandActions`、`proposedExecpolicyAmendment`、`networkApprovalContext` 和 `availableDecisions`。当 `initialize.params.capabilities.experimentalApi = true` 时，载荷还可包含实验性字段 `additionalPermissions`，用于描述每条命令所请求的沙盒访问权限。`additionalPermissions` 中的所有文件系统路径在传输格式中均为绝对路径。
3. 客户端返回上述命令执行审批决定之一。
4. `serverRequest/resolved` 确认待处理的请求已得到响应或已被清除。
5. `item/completed` 返回最终的 `commandExecution` 项，其中包含 `status: completed | failed | declined`。

当存在 `networkApprovalContext` 时，该提示针对的是受管理的网络访问（而非一般的 shell 命令审批）。当前 v2 模式提供目标 `host` 和 `protocol`；客户端应显示专门针对网络访问的提示，不应假定 `command` 是用户可理解的 shell 命令预览。

Codex 按目标（`host`、协议和端口）对并发的网络审批提示进行分组。因此，app-server 可能发送一个提示来放行发往同一目标的多个排队请求；同一主机上的不同端口则会分别处理。

### 文件更改审批

消息顺序：

1. `item/started` 会发送一个 `fileChange` 项，其中包含拟议的 `changes` 和 `status: "inProgress"`。
2. `item/fileChange/requestApproval` 包含 `itemId`、`threadId`、`turnId`，以及可选的 `reason` 和 `grantRoot`。
3. 客户端返回上述文件更改审批决定之一。
4. `serverRequest/resolved` 确认待处理的请求已得到响应或已被清除。
5. `item/completed` 返回最终的 `fileChange` 项，其中包含 `status: completed | failed | declined`。

### `tool/requestUserInput`

当客户端响应 `item/tool/requestUserInput` 时，app-server 会发送包含 `{ threadId, requestId }` 的 `serverRequest/resolved` 通知。如果在客户端响应前，待处理请求因轮次开始、完成或中断而被清除，服务器也会针对这次清理发送相同通知。

请求参数包含 `autoResolutionMs`，其值为以毫秒为单位的整数超时时间或
`null`。若设置了超时时间，且用户未作答，主机客户端可以在该时间间隔过后
自动处理提示。

### 权限请求

内置的 `request_permissions` 工具会发送
`item/permissions/requestApproval`，其中包含 `threadId`、`turnId`、`itemId`、
`environmentId`、`cwd`、可选的 `reason`，以及所请求的网络或文件系统权限。
请在响应中提供 `permissions`，且其中仅包含已授予的权限子集。
将 `scope` 设为 `"session"`，可保留授权，使其在同一会话的后续轮次中继续有效；
省略该字段或使用 `"turn"`，则授权仅对当前轮次有效。
未请求的权限会被忽略。

### MCP 服务器引导式提取请求

MCP 服务器可通过 `mcpServer/elicitation/request` 中断轮次。
请求包含 `threadId`、可选的 `turnId`、`serverName`，以及
以下请求结构之一：

- `mode: "form"` 或 `mode: "openai/form"`，包含 `message` 和
`requestedSchema`。
- `mode: "url"`，包含 `message`、`url` 和 `elicitationId`。

请以 `action: "accept"` 和所请求的 `content` 响应，或以
`action: "decline"` 或 `"cancel"` 配合 `content: null` 响应。App-server 随后会发送
`serverRequest/resolved`。要接收 `openai/form` 变体，请通过
`initialize.params.capabilities.mcpServerOpenaiFormElicitation` 主动启用。

### 动态工具调用（实验性）

`thread/start` 中的 `dynamicTools` 以及相应的 `item/tool/call` 请求或响应流程均为实验性 API。

动态工具名称和命名空间名称必须遵循 Responses API 的命名约束。
请避免使用 Codex 内置工具的保留命名空间名称。

在轮次期间调用动态工具时，app-server 会发送：

1. `item/started`，其中包含 `item.type = "dynamicToolCall"`、`status = "inProgress"`，以及 `tool` 和 `arguments`。
2. `item/tool/call`，作为服务器请求发送给客户端。
3. 包含返回内容项的客户端响应载荷。
4. `item/completed`，其中包含 `item.type = "dynamicToolCall"`、最终的 `status`，以及任何返回的 `contentItems` 或 `success` 值。

### MCP 工具调用审批（应用）

App（连接器）工具调用也可能需要审批。当应用工具调用产生副作用时，服务器可能会通过 `tool/requestUserInput` 请求审批，并提供 **接受**、 **拒绝**和 **取消**等选项。工具的破坏性注解始终会触发审批，即使该工具还提供了表明所需权限较低的提示。如果用户拒绝或取消，相关的 `mcpToolCall` 项会以错误状态结束，不会执行工具。

## 技能

在用户文本输入中包含 `$<skill-name>` 即可调用技能。建议同时添加一个 `skill` 输入项，让服务器注入完整的技能指令，而不是依赖模型解析名称。

```json
{
  "method": "turn/start",
  "id": 101,
  "params": {
    "threadId": "thread-1",
    "input": [
      {
        "type": "text",
        "text": "$skill-creator Add a new skill for triaging flaky CI."
      },
      {
        "type": "skill",
        "name": "skill-creator",
        "path": "/Users/me/.codex/skills/skill-creator/SKILL.md"
      }
    ]
  }
}
```

如果您省略 `skill` 项，模型仍会解析 `$<skill-name>` 标记并尝试查找该技能，这可能会增加延迟。

示例：

```
$skill-creator Add a new skill for triaging flaky CI and include step-by-step usage.
```

使用 `skills/list` 获取可用技能（可通过 `cwds` 限定范围，并支持 `forceReload`）。您还可以传入 `perCwdExtraUserRoots`，针对特定的 `cwd` 值，将额外的绝对路径按 `user` 作用域扫描。App-server 会忽略 `cwd` 不在 `cwds` 中的条目。`skills/list` 可能会复用每个 `cwd` 的缓存结果；设置 `forceReload: true` 可从磁盘刷新。服务器还会从 `SKILL.json` 中读取 `interface` 和 `dependencies`（如果存在）。

```json
{ "method": "skills/list", "id": 25, "params": {
  "cwds": ["/Users/me/project", "/Users/me/other-project"],
  "forceReload": true,
  "perCwdExtraUserRoots": [
    {
      "cwd": "/Users/me/project",
      "extraUserRoots": ["/Users/me/shared-skills"]
    }
  ]
} }
{ "id": 25, "result": {
  "data": [{
    "cwd": "/Users/me/project",
    "skills": [
      {
        "name": "skill-creator",
        "description": "Create or update a Codex skill",
        "enabled": true,
        "interface": {
          "displayName": "Skill Creator",
          "shortDescription": "Create or update a Codex skill"
        },
        "dependencies": {
          "tools": [
            {
              "type": "env_var",
              "value": "GITHUB_TOKEN",
              "description": "GitHub API token"
            },
            {
              "type": "mcp",
              "value": "github",
              "transport": "streamable_http",
              "url": "https://example.com/mcp"
            }
          ]
        }
      }
    ],
    "errors": []
  }]
} }
```

当受监视的本地技能文件发生变化时，服务器还会发送 `skills/changed` 通知。请将其视为失效信号，并在需要时用当前参数重新调用 `skills/list`。

如需按路径启用或禁用技能：

```json
{
  "method": "skills/config/write",
  "id": 26,
  "params": {
    "path": "/Users/me/.codex/skills/skill-creator/SKILL.md",
    "enabled": false
  }
}
```

## 应用（连接器）

使用 `app/installed` 读取已安装应用运行时的最新已提交快照。
每个结果都包含应用的 `id`、`runtimeName`（或 `null`）、实际生效的
`enabled` 状态和 `callable` 状态。只有当生效的配置启用该应用，
且至少有一个对模型可见的工具符合
应用及工具策略时，该应用才可调用。

```json
{
  "method": "app/installed",
  "id": 49,
  "params": {
    "threadId": "thread-1",
    "forceRefresh": false
  }
}
{
  "id": 49,
  "result": {
    "apps": [
      {
        "id": "demo-app",
        "runtimeName": "Demo App",
        "enabled": true,
        "callable": true
      }
    ]
  }
}
```

省略 `threadId` 可使用全局配置，而非已加载线程的配置。
设置 `forceRefresh: true` 可在读取前刷新连接器运行时快照。
当全局或工作空间策略阻止访问应用时，
已发现的应用仍可能显示，但其 `enabled` 和 `callable` 均设为 `false`。

使用 `app/list` 获取可用应用。在 CLI/TUI 中，`/apps` 是面向用户的选择器；在自定义客户端中，请直接调用 `app/list`。每个条目都包含 `isAccessible`（用户可访问）和 `isEnabled`（已在 `config.toml` 中启用），以便客户端区分安装/访问状态与本地启用状态。应用条目还可包含可选的 `branding`、`appMetadata` 和 `labels` 字段。

```json
{ "method": "app/list", "id": 50, "params": {
  "cursor": null,
  "limit": 50,
  "threadId": "thread-1",
  "forceRefetch": false
} }
{ "id": 50, "result": {
  "data": [
    {
      "id": "demo-app",
      "name": "Demo App",
      "description": "Example connector for documentation.",
      "logoUrl": "https://example.com/demo-app.png",
      "logoUrlDark": null,
      "distributionChannel": null,
      "branding": null,
      "appMetadata": null,
      "labels": null,
      "installUrl": "https://chatgpt.com/apps/demo-app/demo-app",
      "isAccessible": true,
      "isEnabled": true
    }
  ],
  "nextCursor": null
} }
```

如果您提供 `threadId`，应用功能的启用检查（`features.apps`）会使用该线程的配置快照。省略时，app-server 使用最新的全局配置。

`app/list` 会在可访问的应用和应用目录中的应用均加载完成后返回。设置 `forceRefetch: true` 可跳过应用缓存并获取最新数据。仅在刷新成功时才会替换缓存条目。

每当任一来源（可访问的应用或应用目录中的应用）加载完成，服务器还会发送 `app/list/updated` 通知。每条通知都包含最新合并的应用列表。

```json
{
  "method": "app/list/updated",
  "params": {
    "data": [
      {
        "id": "demo-app",
        "name": "Demo App",
        "description": "Example connector for documentation.",
        "logoUrl": "https://example.com/demo-app.png",
        "logoUrlDark": null,
        "distributionChannel": null,
        "branding": null,
        "appMetadata": null,
        "labels": null,
        "installUrl": "https://chatgpt.com/apps/demo-app/demo-app",
        "isAccessible": true,
        "isEnabled": true
      }
    ]
  }
}
```

如果您已知应用 ID，并且需要应用元数据而非已安装应用的运行时状态，请使用 `app/read`。
最多传入 100 个 `appIds`。服务器仅保留
每个重复 ID 首次出现的条目，并在
`apps` 和 `missingAppIds` 中保留该顺序。未知或不可访问的应用会在
`missingAppIds` 中返回，不会导致整个请求失败。

```json
{
  "method": "app/read",
  "id": 52,
  "params": {
    "appIds": ["demo-app", "missing-app"],
    "includeTools": true
  }
}
{
  "id": 52,
  "result": {
    "apps": [
      {
        "id": "demo-app",
        "name": "Demo App",
        "description": "Example connector for documentation.",
        "iconUrl": null,
        "iconUrlDark": null,
        "distributionChannel": null,
        "installUrl": null,
        "pluginDisplayNames": [],
        "toolSummaries": [
          {
            "name": "search",
            "title": "Search",
            "description": "Search the app.",
            "isEnabled": true,
            "disabledReason": null,
            "isReadOnly": true
          }
        ]
      }
    ],
    "missingAppIds": ["missing-app"]
  }
}
```

设置 `includeTools: true` 可请求仅供展示的公开工具摘要。
元数据响应不包含已安装应用的运行时状态，也不授予
工具调用权限；请使用 `app/installed` 检查实际生效的 `enabled` 和 `callable`
状态。

在文本输入中插入 `$<app-slug>`，并添加包含 `app://<id>` 路径的 `mention` 输入项（推荐），即可调用应用。

```json
{
  "method": "turn/start",
  "id": 51,
  "params": {
    "threadId": "thread-1",
    "input": [
      {
        "type": "text",
        "text": "$demo-app Pull the latest updates from the team."
      },
      {
        "type": "mention",
        "name": "Demo App",
        "path": "app://demo-app"
      }
    ]
  }
}
```

### 应用设置的配置 RPC 示例

使用 `config/read`、`config/value/write` 和 `config/batchWrite` 查看或更新 `config.toml` 中的应用控制设置。

读取生效的应用配置结构（包括 `_default` 和工具级覆盖设置）：

```json
{ "method": "config/read", "id": 60, "params": { "includeLayers": false } }
{ "id": 60, "result": {
  "config": {
    "apps": {
      "_default": {
        "enabled": true,
        "destructive_enabled": true,
        "open_world_enabled": true,
        "approvals_reviewer": "user",
        "default_tools_approval_mode": "auto"
      },
      "google_drive": {
        "enabled": true,
        "destructive_enabled": false,
        "approvals_reviewer": "auto_review",
        "default_tools_approval_mode": "prompt",
        "tools": {
          "files/delete": { "enabled": false, "approval_mode": "approve" }
        }
      }
    }
  }
} }
```

`apps._default.approvals_reviewer` 为所有应用设置审查者，除非
应用级设置覆盖了该值。如果两者均省略，应用会继承
顶层 `approvals_reviewer` 的值。`apps._default.default_tools_approval_mode`
为没有应用级或工具级覆盖设置的工具
指定后备审批模式。受管审批模式要求会覆盖
工具的审批模式设置。

更新单个应用设置：

```json
{
  "method": "config/value/write",
  "id": 61,
  "params": {
    "keyPath": "apps.google_drive.default_tools_approval_mode",
    "value": "prompt",
    "mergeStrategy": "replace"
  }
}
```

以原子方式应用多项应用配置更改：

```json
{
  "method": "config/batchWrite",
  "id": 62,
  "params": {
    "edits": [
      {
        "keyPath": "apps._default.destructive_enabled",
        "value": false,
        "mergeStrategy": "upsert"
      },
      {
        "keyPath": "apps.google_drive.tools.files/delete.approval_mode",
        "value": "approve",
        "mergeStrategy": "upsert"
      }
    ]
  }
}
```

### 检测并导入外部智能体配置

使用 `externalAgentConfig/detect` 查找可迁移的外部智能体产物，然后将所选条目传递给 `externalAgentConfig/import`。

检测示例：

```json
{ "method": "externalAgentConfig/detect", "id": 63, "params": {
  "includeHome": true,
  "cwds": ["/Users/me/project"]
} }
{ "id": 63, "result": {
  "items": [
    {
      "itemType": "AGENTS_MD",
      "description": "Import /Users/me/project/CLAUDE.md to /Users/me/project/AGENTS.md.",
      "cwd": "/Users/me/project"
    },
    {
      "itemType": "SKILLS",
      "description": "Copy skill folders from /Users/me/.claude/skills to /Users/me/.agents/skills.",
      "cwd": null
    }
  ]
} }
```

导入示例：

```json
{ "method": "externalAgentConfig/import", "id": 64, "params": {
  "migrationItems": [
    {
      "itemType": "AGENTS_MD",
      "description": "Import /Users/me/project/CLAUDE.md to /Users/me/project/AGENTS.md.",
      "cwd": "/Users/me/project"
    }
  ],
  "source": "claude-code"
} }
{ "id": 64, "result": { "importId": "8ae96ff3-3425-4f4c-8772-b6fd61502868" } }
```

可选的顶层 `source` 导入参数用于标识
生成所选迁移项的产品。

服务器会在各类型的导入完成时发出 `externalAgentConfig/import/progress`，
并在所有同步和后台导入完成后
发出 `externalAgentConfig/import/completed`。这些通知包含与响应相同的 `importId`，
以及包含各类型 `successes` 和 `failures` 的 `itemTypeResults`。
完成通知可能在响应后立即到达，也可能在后台远程
导入完成后到达。

```json
{ "method": "externalAgentConfig/import/progress", "params": {
  "importId": "8ae96ff3-3425-4f4c-8772-b6fd61502868",
  "itemTypeResults": [
    {
      "itemType": "AGENTS_MD",
      "successes": [
        { "itemType": "AGENTS_MD", "cwd": "/Users/me/project", "source": null, "target": "/Users/me/project/AGENTS.md" }
      ],
      "failures": []
    }
  ]
} }
{ "method": "externalAgentConfig/import/completed", "params": {
  "importId": "8ae96ff3-3425-4f4c-8772-b6fd61502868",
  "itemTypeResults": [
    {
      "itemType": "AGENTS_MD",
      "successes": [
        { "itemType": "AGENTS_MD", "cwd": "/Users/me/project", "source": null, "target": "/Users/me/project/AGENTS.md" }
      ],
      "failures": []
    }
  ]
} }
```

读取此前已完成的导入：

```json
{ "method": "externalAgentConfig/import/readHistories", "id": 65 }
{ "id": 65, "result": { "data": [
  {
    "importId": "8ae96ff3-3425-4f4c-8772-b6fd61502868",
    "completedAtMs": 1781784000000,
    "successes": [
      { "itemType": "AGENTS_MD", "cwd": "/Users/me/project", "source": null, "target": "/Users/me/project/AGENTS.md" }
    ],
    "failures": []
  }
] } }
```

支持的 `itemType` 值为 `AGENTS_MD`、`CONFIG`、`SKILLS`、`PLUGINS`、
`MCP_SERVER_CONFIG`、`SUBAGENTS`、`HOOKS`、`COMMANDS` 和 `SESSIONS`。
对于 `PLUGINS` 项，`details.plugins` 会列出每个 `marketplaceName` 以及
Codex 可尝试迁移的 `pluginNames`。检测只会返回
仍需处理的项。例如，如果 `AGENTS.md`
已存在且非空，Codex 会跳过 AGENTS 迁移；导入技能时不会覆盖
现有的技能目录。

从 `.claude/settings.json` 检测插件时，Codex 会从
`extraKnownMarketplaces` 中读取已配置的市场来源。如果 `enabledPlugins` 包含
来自 `claude-plugins-official` 的插件，但缺少相应的市场来源，
Codex 会推断其来源为 `anthropics/claude-plugins-official`。

## 身份验证端点

JSON-RPC 身份验证与账户接口提供请求和响应方法，以及服务器发起的通知（不含 `id`）。使用这些接口可确定身份验证状态、开始或取消登录、退出登录、查看 ChatGPT 速率限制，以及在额度耗尽或达到用量限制时通知工作空间所有者。

### 身份验证模式

Codex 支持以下身份验证模式。`account/updated.authMode` 显示当前模式，并在可用时包含当前 ChatGPT 的 `planType`。`account/read` 也会报告账户和套餐详情。

- **API 密钥（`apikey`）** ：调用方通过 `type: "apiKey"` 提供 OpenAI API 密钥，Codex 会存储该密钥，以供 API 请求使用。
- **ChatGPT 托管（`chatgpt`）** ：Codex 负责 ChatGPT OAuth 流程，持久化存储 Token 并自动刷新。使用 `type: "chatgpt"` 启动浏览器流程，或使用 `type: "chatgptDeviceCode"` 启动设备代码流程。
- **ChatGPT 外部 Token（`chatgptAuthTokens`）** ：此实验性模式适用于已负责用户 ChatGPT 身份验证生命周期的主机应用。主机应用直接提供 `accessToken`、`chatgptAccountId` 和可选的 `chatgptPlanType`，并且必须在收到请求时刷新 Token。
- **Amazon Bedrock** ：`account/read` 将 Bedrock 账户报告为 `type: "amazonBedrock"`，并指明凭证来自 Codex 管理的 Bedrock API 密钥（`credentialSource: "codexManaged"`）还是外部 AWS 凭证链（`credentialSource: "awsManaged"`）。对于 Codex 管理的 Bedrock API 密钥，`account/updated.authMode` 使用 `bedrockApiKey`。

### API 概览

- `account/read`：获取当前账户信息；可选择刷新 Token。
- `account/login/start`：开始登录（`apiKey`、`chatgpt`、`chatgptDeviceCode` 或实验性的 `chatgptAuthTokens`）。
- `account/login/completed`（通知）：登录尝试结束时发出，无论成功还是出错。
- `account/login/cancel`：通过 `loginId` 取消待完成的 ChatGPT 托管登录。
- `account/logout`：退出登录；触发 `account/updated`。
- `account/updated`（通知）：每当身份验证模式发生变化（`authMode`：`apikey`、`chatgpt`、`chatgptAuthTokens`、`agentIdentity`、`personalAccessToken`、`bedrockApiKey` 或 `null`）时发出，并在可用时包含 `planType`。
- `account/chatgptAuthTokens/refresh`（服务器请求）：发生授权错误后，请求由外部管理的新 ChatGPT Token。
- `account/rateLimits/read`：获取 ChatGPT 速率限制。
- `account/rateLimits/updated`（通知）：每当用户的 ChatGPT 速率限制发生变化时发出。
- `account/sendAddCreditsNudgeEmail`：请求 ChatGPT 向工作空间所有者发送电子邮件，告知额度已耗尽或已达到用量限制。
- `account/rateLimitResetCredit/consume`：使用调用方提供的 `idempotencyKey` 值，消耗一次已获得的速率限制重置机会。
- `account/usage/read`：获取 ChatGPT 账户的 Token 活动摘要及按日分桶的数据。
- `account/workspaceMessages/read`：获取当前有效的工作空间消息，并在有通知标题时一并返回。
- `mcpServer/oauthLogin/completed`（通知）：在 `mcpServer/oauth/login` 流程完成后发出；有效载荷包含 `{ name, threadId, success, error? }`。对于应用级或插件 OAuth 流程，`threadId` 可以为 `null`。
- `mcpServer/startupStatus/updated`（通知）：已配置的 MCP 服务器启动状态发生变化时发出；有效载荷包含 `{ threadId, name, status, error, failureReason }`。对于应用级启动，`threadId` 为 `null`。启动失败时，`failureReason: "reauthenticationRequired"` 表示存储的 OAuth 凭证已过期且无法刷新，因此客户端应提供重新连接该服务器的选项。

### 1) 检查身份验证状态

请求：

```json
{ "method": "account/read", "id": 1, "params": { "refreshToken": false } }
```

响应示例：

```json
{ "id": 1, "result": { "account": null, "requiresOpenaiAuth": false } }
```

```json
{ "id": 1, "result": { "account": null, "requiresOpenaiAuth": true } }
```

```json
{
  "id": 1,
  "result": { "account": { "type": "apiKey" }, "requiresOpenaiAuth": true }
}
```

```json
{
  "id": 1,
  "result": {
    "account": {
      "type": "amazonBedrock",
      "credentialSource": "codexManaged"
    },
    "requiresOpenaiAuth": false
  }
}
```

```json
{
  "id": 1,
  "result": {
    "account": {
      "type": "amazonBedrock",
      "credentialSource": "awsManaged"
    },
    "requiresOpenaiAuth": false
  }
}
```

```json
{
  "id": 1,
  "result": {
    "account": {
      "type": "chatgpt",
      "email": "user@example.com",
      "planType": "pro"
    },
    "requiresOpenaiAuth": true
  }
}
```

字段说明：

- `refreshToken`（布尔值）：设置为 `true` 可在 ChatGPT 托管模式下强制刷新 Token。在外部 Token 模式（`chatgptAuthTokens`）下，app-server 会忽略此标志。
- 当 ChatGPT 账户没有电子邮件地址时，`email` 为 `null`。
- `requiresOpenaiAuth` 反映当前使用的提供商；当其为 `false` 时，Codex 无需 OpenAI 凭证即可运行。
- Amazon Bedrock 使用由 Codex 管理的 Bedrock API 密钥时，会报告 `credentialSource: "codexManaged"`。
  使用外部 AWS 凭证获取方式时，会报告 `credentialSource: "awsManaged"`。
  这用于标识所选的凭证来源，
  但不会验证 AWS 凭证链能否
  解析出凭证。

### 2) 使用 API 密钥登录

1. 发送：

   ```json
   {
     "method": "account/login/start",
     "id": 2,
     "params": { "type": "apiKey", "apiKey": "sk-..." }
   }
   ```

2. 预期响应：

   ```json
   { "id": 2, "result": { "type": "apiKey" } }
   ```

3. 通知：

   ```json
   {
     "method": "account/login/completed",
     "params": { "loginId": null, "success": true, "error": null }
   }
   ```

   ```json
   {
     "method": "account/updated",
     "params": { "authMode": "apikey", "planType": null }
   }
   ```

### 3) 使用 ChatGPT 登录（浏览器流程）

1. 开始：

   ```json
   {
     "method": "account/login/start",
     "id": 3,
     "params": {
       "type": "chatgpt",
       "useHostedLoginSuccessPage": true,
       "appBrand": "chatgpt"
     }
   }
   ```

   默认情况下，浏览器回调成功后会重定向到本地成功页面。
   设置 `useHostedLoginSuccessPage: true` 后，
   在无需设置组织的情况下会使用托管的成功页面。启用托管成功页面后，`appBrand`
   可以为 `"codex"` 或 `"chatgpt"`；省略该值或值为 `null` 时，默认为
`"codex"`。

   ```json
   {
     "id": 3,
     "result": {
       "type": "chatgpt",
       "loginId": "<uuid>",
       "authUrl": "https://chatgpt.com/...&redirect_uri=http%3A%2F%2Flocalhost%3A<port>%2Fauth%2Fcallback"
     }
   }
   ```

2. 在浏览器中打开 `authUrl`；app-server 会托管本地回调。
3. 等待通知：

   ```json
   {
     "method": "account/login/completed",
     "params": { "loginId": "<uuid>", "success": true, "error": null }
   }
   ```

   ```json
   {
     "method": "account/updated",
     "params": { "authMode": "chatgpt", "planType": "plus" }
   }
   ```

### 3b) 使用 ChatGPT 登录（设备代码流程）

如果登录流程由您的客户端负责，或浏览器回调不够可靠，请使用此流程。

1. 开始：

   ```json
   {
     "method": "account/login/start",
     "id": 4,
     "params": { "type": "chatgptDeviceCode" }
   }
   ```

   ```json
   {
     "id": 4,
     "result": {
       "type": "chatgptDeviceCode",
       "loginId": "<uuid>",
       "verificationUrl": "https://auth.openai.com/codex/device",
       "userCode": "ABCD-1234"
     }
   }
   ```

2. 向用户显示 `verificationUrl` 和 `userCode`；用户体验由前端负责。
3. 等待通知：

   ```json
   {
     "method": "account/login/completed",
     "params": { "loginId": "<uuid>", "success": true, "error": null }
   }
   ```

   ```json
   {
     "method": "account/updated",
     "params": { "authMode": "chatgpt", "planType": "plus" }
   }
   ```

### 3c) 使用外部管理的 ChatGPT Token 登录（`chatgptAuthTokens`）

仅当主机应用负责管理用户的 ChatGPT 身份验证生命周期，并直接提供 Token 时，才使用此实验性模式。客户端必须先在 `initialize` 期间设置 `capabilities.experimentalApi = true`，才能使用此登录类型。

1. 发送：

   ```json
   {
     "method": "account/login/start",
     "id": 7,
     "params": {
       "type": "chatgptAuthTokens",
       "accessToken": "<jwt>",
       "chatgptAccountId": "org-123",
       "chatgptPlanType": "business"
     }
   }
   ```

2. 预期响应：

   ```json
   { "id": 7, "result": { "type": "chatgptAuthTokens" } }
   ```

3. 通知：

   ```json
   {
     "method": "account/login/completed",
     "params": { "loginId": null, "success": true, "error": null }
   }
   ```

   ```json
   {
     "method": "account/updated",
     "params": { "authMode": "chatgptAuthTokens", "planType": "business" }
   }
   ```

服务器收到 `401 Unauthorized` 时，可能会向主机应用请求刷新后的 Token：

```json
{
  "method": "account/chatgptAuthTokens/refresh",
  "id": 8,
  "params": { "reason": "unauthorized", "previousAccountId": "org-123" }
}
{ "id": 8, "result": { "accessToken": "<jwt>", "chatgptAccountId": "org-123", "chatgptPlanType": "business" } }
```

收到成功的刷新响应后，服务器会重试原始请求。请求约在 10 秒后超时。

### 4) 取消 ChatGPT 登录

```json
{ "method": "account/login/cancel", "id": 4, "params": { "loginId": "<uuid>" } }
{ "method": "account/login/completed", "params": { "loginId": "<uuid>", "success": false, "error": "..." } }
```

### 5) 退出登录

```json
{ "method": "account/logout", "id": 5 }
{ "id": 5, "result": {} }
{ "method": "account/updated", "params": { "authMode": null, "planType": null } }
```

### 6) 速率限制（ChatGPT）

```json
{ "method": "account/rateLimits/read", "id": 6 }
{ "id": 6, "result": {
  "rateLimits": {
    "limitId": "codex",
    "limitName": null,
    "primary": { "usedPercent": 25, "windowDurationMins": 15, "resetsAt": 1730947200 },
    "secondary": null,
    "rateLimitReachedType": null
  },
  "rateLimitsByLimitId": {
    "codex": {
      "limitId": "codex",
      "limitName": null,
      "primary": { "usedPercent": 25, "windowDurationMins": 15, "resetsAt": 1730947200 },
      "secondary": null,
      "rateLimitReachedType": null
    },
    "codex_other": {
      "limitId": "codex_other",
      "limitName": "codex_other",
      "primary": { "usedPercent": 42, "windowDurationMins": 60, "resetsAt": 1730950800 },
      "secondary": null,
      "rateLimitReachedType": null
    }
  },
  "rateLimitResetCredits": {
    "availableCount": 2,
    "credits": [{
      "id": "RateLimitResetCredit_1",
      "resetType": "codexRateLimits",
      "status": "available",
      "grantedAt": 1781654400,
      "expiresAt": 1784246400,
      "title": "Rate-limit reset",
      "description": "Reset an eligible Codex rate-limit window."
    }]
  }
} }
{ "method": "account/rateLimits/updated", "params": {
  "rateLimits": {
    "limitId": "codex",
    "primary": { "usedPercent": 31, "windowDurationMins": 15, "resetsAt": 1730948100 }
  }
} }
```

字段说明：

- `rateLimits` 是向后兼容的单限额桶视图。
- `rateLimitsByLimitId`（如存在）是多限额桶视图，以用于计量的 `limit_id`（例如 `codex`）为键。
- `limitId` 是计量限额桶的标识符。
- `limitName` 是该限额桶面向用户的可选标签。
- `usedPercent` 是配额窗口内的当前使用率。
- `windowDurationMins` 是配额窗口的时长。
- `resetsAt` 是下一次重置时间的 Unix 时间戳（秒）。
- 服务器返回与限额桶关联的 ChatGPT 套餐时，响应中会包含 `planType`。
- 服务器返回工作空间剩余额度的详细信息时，响应中会包含 `credits`。
- 达到限额时，`rateLimitReachedType` 用于标识服务器判定的限额状态。
- 服务提供相关数据时，`rateLimitResetCredits` 包含已获得且可用的重置次数；否则为 `null`。
- 如果只知道数量，`rateLimitResetCredits.credits` 为 `null`。空数组表示服务已获取详细信息，返回结果中没有可用额度。服务可能限制返回的明细行数，因此应以 `availableCount` 为准。
- 每条明细记录均包含一个不透明的 `id`，以及 `resetType`、`status`、`grantedAt`、`expiresAt`（可为 `null`）、`title`（可为 `null`）和 `description`（可为 `null`）。
- 消耗一次重置额度后，请调用 `account/rateLimits/read`。

### 7) Token 用量（ChatGPT）

使用 `account/usage/read` 获取 ChatGPT 的 Token 活动摘要字段和
可选的每日分桶数据。

```json
{ "method": "account/usage/read", "id": 7 }
{ "id": 7, "result": {
  "summary": {
    "lifetimeTokens": 1234567,
    "peakDailyTokens": 45678,
    "longestRunningTurnSec": 540,
    "currentStreakDays": 8,
    "longestStreakDays": 14
  },
  "dailyUsageBuckets": [
    { "startDate": "2026-06-18", "tokens": 12345 }
  ]
} }
```

字段说明：

- 服务尚未返回相应指标时，`summary` 中的值可能为 `null`。
- `dailyUsageBuckets` 可能为 `null`；如存在，每个分桶都包含 `startDate` 和 `tokens`。
- 此端点需要由 Codex 服务支持的身份验证。ChatGPT、
外部 ChatGPT Token、智能体身份和个人访问 Token 身份验证均可用；
仅使用 API 密钥的身份验证和 Bedrock 身份验证不可用。

### 8) 已获得的速率限制重置机会（ChatGPT）

使用 `account/rateLimitResetCredit/consume` 消耗一次已获得的重置机会。

```json
{ "method": "account/rateLimitResetCredit/consume", "id": 8, "params": { "idempotencyKey": "8ae96ff3-3425-4f4c-8772-b6fd61502868", "creditId": "RateLimitResetCredit_1" } }
{ "id": 8, "result": { "outcome": "reset" } }
```

字段说明：

- `idempotencyKey` 不得为空。为每次独立的兑换尝试使用一个 UUID，重试同一次尝试时复用该值。
- `creditId` 是可选字段。提供时，它必须是来自 `account/rateLimits/read` 的非空不透明 ID。省略时，服务会选择下一项可用额度。
- `reset` 表示已消耗一项重置额度。
- `alreadyRedeemed` 表示同一兑换操作此前已完成。请将其视为幂等成功，并刷新账户限额。
- `nothingToReset` 表示没有符合条件的速率限制窗口可供重置。
- `noCredit` 表示账户没有已获得且可用的重置额度。
- 消耗一次重置额度后，请调用 `account/rateLimits/read`，不要根据此响应推断更新后的窗口。

### 9) 向工作空间所有者发送限额通知

额度耗尽或达到使用限额时，使用 `account/sendAddCreditsNudgeEmail` 请求 ChatGPT 向工作空间所有者发送电子邮件。

```json
{ "method": "account/sendAddCreditsNudgeEmail", "id": 9, "params": { "creditType": "credits" } }
{ "id": 9, "result": { "status": "sent" } }
```

工作空间额度耗尽时使用 `creditType: "credits"`，达到工作空间使用限额时使用 `creditType: "usage_limit"`。如果近期已通知过所有者，响应状态为 `cooldown_active`。

### 10) 工作空间消息（ChatGPT）

使用 `account/workspaceMessages/read` 获取当前工作空间中处于活动状态的消息，
包括通知标题（如有）。

```json
{ "method": "account/workspaceMessages/read", "id": 10 }
{ "id": 10, "result": { "featureEnabled": true, "messages": [
  { "messageId": "msg_123", "messageType": "headline", "messageBody": "Workspace maintenance starts at 5pm.", "createdAt": 1781395200, "archivedAt": null }
] } }
```