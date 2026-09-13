# MivoAi Web


Next.js App Router + React + TypeScript。前端按业务功能划分，路由和展示层不直接处理网络协议。

## 本地运行

在 `apps/web` 中运行：

```powershell
npm install
npm run dev
```

前端默认 `http://localhost:3000`，API 默认 `http://127.0.0.1:8000`。
HTTP `/api/*` 通过 Next.js rewrite 转发，聊天通过浏览器直接连接后端 WebSocket。
`NEXT_PUBLIC_API_WS_URL` 可覆盖连接基址；HTTPS 默认同域 `wss://`，由反向代理转发 Upgrade。
公开变量在构建时内联，修改后需要重启开发服务或重新构建。后端 Origin 白名单需包含前端来源。

## 目录与依赖

```text
app/                         路由、布局、全局样式入口
widgets/workspace/           跨功能组合与页面级布局
features/chat/
  api/                       会话 HTTP API、会话级 WebSocket 客户端
  hooks/                     生命周期与会话用例
  model/                     可独立测试的消息状态转换
  components/                输入框、消息列表、会话导航
  types.ts                   会话和事件协议类型
features/models/             模型配置 API、Hook、设置面板、类型
features/system/             后端健康状态查询
features/inspiration/        灵感数据与展示
shared/api/                  HTTP 客户端、公共错误处理
shared/ui/                   无业务依赖的公共 UI
scripts/                     架构检查
tests/                       协议与纯函数测试
```

依赖方向为 `app -> widgets -> features -> shared`。
功能之间不直接导入内部实现；由 widget 组合并传入明确类型的 props。
`shared` 不依赖业务模块，API 模块不依赖 React；组件不能直接调用 fetch/WebSocket。
新增业务按功能扩展，避免建立全项目共享的大型 hooks、types 或 services 文件。

路由保持 Server Component；仅交互入口、Hook 和交互组件使用 `use client`。
服务端数据由功能 Hook 管理，输入框、抽屉、折叠等 UI 状态就近存放。
网络错误必须呈现给用户；异步加载支持取消，旧请求不能覆盖新会话。
当前保留既有全局样式以保持视觉一致，新增独立功能优先使用 CSS Modules；
不要将业务样式、网络逻辑或静态样例数据追加到 `app/page.tsx`。

## 会话协议

每个选中的会话拥有一个 `SessionSocket`，连续回合复用连接。`done` 结束回合而不关闭连接。
切换会话或卸载组件时释放连接与定时器；断线拒绝活动请求，不自动重发消息。
重新连接会读取持久化历史。连接以 20 秒 ping/pong 心跳检测失联。

`meta` 关联消息 ID，`output` 提供分离的 `content` 和 `reasoning` 快照；
后端按 Codex `itemId`、`phase` 聚合，思考过程和最终回答独立显示。
事件携带 `clientMessageId`，防止过期回合事件污染当前回复。
不再使用 SSE。后端与 Codex 仍使用持续输出的 stdio JSON-RPC。

## 检查

```powershell
npm run typecheck
npm run check:architecture
npm test
npm run build
```

架构检查通过 Babel 的 TypeScript AST 验证依赖方向及网络调用归属。
测试覆盖连接复用、断线、取消连接、阶段内容更新；后端另有 WebSocket 集成测试。
测试使用 Node 内置测试运行器和 tsx 转译，不添加运行时状态管理依赖。
