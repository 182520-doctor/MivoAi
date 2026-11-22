require("./register-typescript.cjs");
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { SessionSocket } = require("../features/chat/api/session-socket.ts");

class FakeSocket {
  readyState = 0;
  sent = [];
  send(text) {
    this.sent.push(JSON.parse(text));
  }
  emit(event) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

test("one session connection handles two turns, errors and interrupt", async () => {
  const sockets = [];
  const client = new SessionSocket(
    "ws://test",
    () => {},
    () => {},
    () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
  );
  try {
    const ready = client.connect();
    const socket = sockets[0];
    socket.readyState = 1;
    socket.emit({ type: "ready", conversationId: "c" });
    await ready;
    for (const id of ["one", "two"]) {
      await client.connect();
      const events = [];
      const completion = client.send(
        { clientMessageId: id, message: id },
        (event) => events.push(event),
      );
      socket.emit({
        type: "output",
        clientMessageId: "stale",
        content: "wrong",
        reasoning: "",
      });
      socket.emit({
        type: "output",
        clientMessageId: id,
        content: "answer",
        reasoning: "progress",
      });
      socket.emit({ type: "done", clientMessageId: id, status: "completed" });
      await completion;
      assert.equal(events.length, 2);
      assert.equal(socket.readyState, 1);
    }
    assert.equal(sockets.length, 1);
    const rejected = client.send({ clientMessageId: "bad" }, () => {});
    socket.emit({
      type: "error",
      clientMessageId: "bad",
      message: "Invalid model",
    });
    await assert.rejects(rejected, /Invalid model/);
    const pending = client.send({ clientMessageId: "stop" }, () => {});
    client.interrupt();
    assert.deepEqual(socket.sent.at(-1), { type: "interrupt" });
    socket.emit({
      type: "done",
      clientMessageId: "stop",
      status: "interrupted",
    });
    await pending;
    assert.equal(sockets.length, 1);
  } finally {
    client.close();
  }
});

test("disconnect rejects an active turn and never replays it", async () => {
  const sockets = [];
  const client = new SessionSocket(
    "ws://test",
    () => {},
    () => {},
    () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
  );
  try {
    const ready = client.connect();
    sockets[0].readyState = 1;
    sockets[0].emit({ type: "ready" });
    await ready;
    const turn = client.send({ clientMessageId: "one" }, () => {});
    sockets[0].close();
    await assert.rejects(turn, /断开/);
    const reconnect = client.connect();
    sockets[1].readyState = 1;
    sockets[1].emit({ type: "ready" });
    await reconnect;
    assert.equal(sockets[1].sent.length, 0);
  } finally {
    client.close();
  }
});

test("closing during connection rejects readiness and clears resources", async () => {
  const client = new SessionSocket(
    "ws://test",
    () => {},
    () => {},
    () => new FakeSocket(),
  );
  const ready = client.connect();
  client.close();
  await assert.rejects(ready, /关闭/);
});
