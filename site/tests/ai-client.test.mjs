import { test } from "node:test";
import assert from "node:assert/strict";
import { apiClient, validateEndpoint } from "../github-pages/api-client.ts";

test("AI endpoint permits HTTPS or loopback without embedded credentials", () => {
  assert.equal(validateEndpoint("http://127.0.0.1:8000"), "http://127.0.0.1:8000");
  assert.equal(validateEndpoint("https://api.example.test/"), "https://api.example.test");
  for (const input of ["http://remote.example", "javascript:alert(1)", "https://user:secret@example.test", "https://example.test/api", "https://example.test/?token=x"]) {
    assert.throws(() => validateEndpoint(input));
  }
});

test("AI client sends the question to the selected API and preserves cancellation", async () => {
  const original = globalThis.fetch;
  const signal = new AbortController().signal;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://localhost:8000/api/ask");
    assert.equal(options.signal, signal);
    assert.deepEqual(JSON.parse(options.body), { question: "What is due care?" });
    return new Response(JSON.stringify({ mode: "rag", answer: "Care and skill. [1]" }));
  };
  try {
    const result = await apiClient("http://localhost:8000").ask("What is due care?", signal);
    assert.equal(result.mode, "rag");
  } finally { globalThis.fetch = original; }
});

test("AI failure stays visible instead of silently becoming a browser answer", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Local model unavailable" }), { status: 503 });
  try {
    await assert.rejects(apiClient("http://localhost:8000").ask("care?", new AbortController().signal), /Local model unavailable/);
  } finally { globalThis.fetch = original; }
});
