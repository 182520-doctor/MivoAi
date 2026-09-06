import { test, expect } from "@playwright/test";

test("session socket streams progress and answers across desktop and mobile", async ({
  page,
}) => {
  let sockets = 0;
  let turns = 0;
  let sseRequests = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/messages"))
      sseRequests++;
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname === "/api/status")
      body = {
        status: "ok",
        app_server: { running: true, authenticated: true },
      };
    else if (url.pathname === "/api/models")
      body = [
        {
          id: "codex-local-default",
          providerId: "codex_local",
          providerName: "Codex",
          name: "Codex",
          configured: true,
          capabilities: ["text"],
          integrationStatus: "ready",
        },
      ];
    else if (url.pathname === "/api/preferences")
      body = { defaultTextModelId: "codex-local-default" };
    else if (url.pathname === "/api/conversations")
      body =
        route.request().method() === "POST"
          ? { id: "session-1", title: "Test" }
          : [];
    await route.fulfill({ json: body });
  });
  await page.routeWebSocket("**/api/conversations/*/ws", (socket) => {
    sockets++;
    socket.send(JSON.stringify({ type: "ready", conversationId: "session-1" }));
    socket.onMessage((raw) => {
      const command = JSON.parse(String(raw));
      if (command.type === "ping") {
        socket.send(JSON.stringify({ type: "pong" }));
        return;
      }
      if (command.type !== "message") return;
      turns++;
      const requestId = command.payload.clientMessageId;
      const send = (event: object) =>
        socket.send(JSON.stringify({ ...event, clientMessageId: requestId }));
      send({ type: "meta", assistantMessageId: `answer-${turns}` });
      send({ type: "output", content: "", reasoning: "Checking requirements" });
      setTimeout(
        () =>
          send({
            type: "output",
            content: "Final answer",
            reasoning: "Checking requirements",
          }),
        400,
      );
      setTimeout(() => send({ type: "done", status: "completed" }), 600);
    });
  });
  await page.goto(process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3001");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("textbox", { name: "发送消息" }).fill("hello");
    await page.getByRole("button", { name: "发送消息", exact: true }).click();
    const answer = page.locator(".message.assistant").last();
    await expect(answer.locator(".reasoning-body")).toContainText(
      "Checking requirements",
    );
    await expect(answer.locator(".markdown")).toContainText("Final answer");
    await expect(answer.locator(".message-status")).toContainText("已完成");
    await expect(answer.locator(".markdown")).not.toContainText(
      "Checking requirements",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/chat-${width}.png`,
      fullPage: true,
    });
  }
  expect(sockets).toBe(1);
  expect(turns).toBe(2);
  expect(sseRequests).toBe(0);
});
