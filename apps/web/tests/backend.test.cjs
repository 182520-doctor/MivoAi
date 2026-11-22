require("./register-typescript.cjs");
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { apiUrl } = require("../shared/api/backend.ts");

test("frontend API requests go directly to FastAPI port 8010", () => {
  const previous = process.env.NEXT_PUBLIC_API_BASE_URL;
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  try {
    assert.equal(
      apiUrl("/api/status"),
      "http://127.0.0.1:8010/api/status",
    );
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
    else process.env.NEXT_PUBLIC_API_BASE_URL = previous;
  }
});

test("absolute media URLs are not rewritten", () => {
  assert.equal(
    apiUrl("https://example.test/image.png"),
    "https://example.test/image.png",
  );
});
