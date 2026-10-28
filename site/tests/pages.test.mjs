import { test } from "node:test";
import assert from "node:assert/strict";
import { browserClient } from "../github-pages/browser-client.ts";
import { ask, status } from "../lib/engine.mjs";

test("Pages loads the active collection and matching evaluation", async () => {
  const collection = await browserClient.status();
  const evaluation = await browserClient.evaluation();
  assert.deepEqual(collection, status());
  assert.equal(collection.corpus_sha256, evaluation.corpus_sha256);
  assert.equal(evaluation.results.length, evaluation.metrics.questions);
});

test("Pages answers locally without making network requests", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error("Pages must not call a backend"); };
  try {
    const question = "What guarantee applies to services supplied with due care and skill?";
    const { latency_ms, ...result } = await browserClient.ask(question, new AbortController().signal);
    assert.deepEqual(result, ask(question));
    assert.equal(result.evidence[0].id, "acl-s60");
    assert.ok(latency_ms >= 0);
  } finally { globalThis.fetch = originalFetch; }
});

test("Pages respects cancelled requests", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(browserClient.ask("consumer guarantees", controller.signal), { name: "AbortError" });
});
