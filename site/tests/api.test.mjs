import { registerHooks } from "node:module";
import { test } from "node:test";
import assert from "node:assert/strict";

registerHooks({ resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) return nextResolve(new URL(`../${specifier.slice(2)}`, import.meta.url).href, context);
  return nextResolve(specifier, context);
} });
const { POST } = await import("../app/api/ask/route.ts");
const { GET: getStatus } = await import("../app/api/status/route.ts");
// The evaluation route's JSON import is handled by Vite in production, so its
// response is tested through the running server in browser QA.
const request = (body, headers = {}) => new Request("https://example.test/api/ask", {
  method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body),
});

test("API returns cited passages and measured latency", async () => {
  const response = await POST(request({ question: "What guarantee applies to services supplied with due care and skill?" }));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.abstained, false); assert.equal(body.evidence[0].id, "acl-s60");
  assert.equal(body.evidence[0].source_kind, "legislation_extract");
  assert.match(body.answer, /\[1\]/); assert.ok(body.latency_ms >= 0);
  assert.equal(response.headers.get("cache-control"), "no-store");
});
test("API declines out-of-scope questions", async () => {
  const response = await POST(request({ question: "What is the current NCAT application fee in Sydney?" }));
  assert.equal((await response.json()).abstained, true);
});
test("API validates body shape and question limits", async () => {
  for (const body of [null, [], {}, { question: 1 }, { question: " " }, { question: "x".repeat(2001) }]) {
    assert.equal((await POST(request(body))).status, 400);
  }
});
test("API rejects malformed JSON and oversized bodies", async () => {
  assert.equal((await POST(new Request("https://example.test/api/ask", { method: "POST", headers: { "content-type": "application/json" }, body: "{" }))).status, 400);
  assert.equal((await POST(request({ question: "x".repeat(10001) }))).status, 413);
});
test("API rejects cross-origin requests", async () => {
  assert.equal((await POST(request({ question: "warranty" }, { origin: "https://other.test" }))).status, 403);
  assert.equal((await POST(request({ question: "warranty" }, { origin: "https://example.test" }))).status, 200);
});
test("API requires JSON content type", async () => {
  assert.equal((await POST(request({}, { "content-type": "text/plain" }))).status, 415);
});
test("Health endpoint reports the active corpus", async () => {
  const response = getStatus(); assert.equal(response.status, 200);
  const body = await response.json(); assert.equal(body.status, "ok"); assert.equal(body.sources.length, body.section_count);
  assert.equal(body.collection.dataset, "cchew/lex-au"); assert.equal(body.law_count, 1);
});
