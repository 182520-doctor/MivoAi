require("./register-typescript.cjs");
const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  applyMessageEvent,
} = require("../features/chat/model/message-events.ts");

test("stream snapshots keep progress separate and replace rather than duplicate text", () => {
  const initial = {
    id: "local",
    role: "assistant",
    content: "",
    status: "streaming",
  };
  let message = applyMessageEvent(initial, {
    type: "meta",
    assistantMessageId: "saved",
  });
  message = applyMessageEvent(message, {
    type: "output",
    content: "",
    reasoning: "Checking",
  });
  assert.equal(message.content, "");
  message = applyMessageEvent(message, {
    type: "output",
    content: "Answer",
    reasoning: "Checking",
  });
  message = applyMessageEvent(message, {
    type: "output",
    content: "Answer",
    reasoning: "Checking",
  });
  message = applyMessageEvent(message, { type: "done", status: "completed" });
  assert.deepEqual(message, {
    ...initial,
    id: "saved",
    content: "Answer",
    reasoning: "Checking",
    status: "done",
  });
  assert.equal(initial.content, "");
});
