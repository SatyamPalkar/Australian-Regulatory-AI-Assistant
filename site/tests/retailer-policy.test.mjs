import { test } from "node:test";
import assert from "node:assert/strict";
import { policyAnswer, policyPassages, retailerIntent, contentURL } from "../lib/retailer-policy.mjs";
import { browserClient } from "../github-pages/browser-client.ts";

const paragraph = value => ({ nodeType: "paragraph", content: [{ nodeType: "text", value }] });
const row = (...values) => ({ nodeType: "table-row", content: values.map(paragraph) });
const fixture = () => ({ data: { items: [{ fields: {
  legacyId: "360053005194", heading: "Refunds & Warranties guide", mainBody: { content: [
    paragraph("This Guide applies to direct purchases. Marketplace sellers have separate terms."),
    paragraph("Our goods come with guarantees. Faults require assessment."),
    { nodeType: "table", content: [row("Status", "Limit", "Exclusions"), row("Unused & Unopened", "Test period", "Commercial excluded")] },
    { nodeType: "heading-2", content: [{ nodeType: "text", value: "Media products" }] },
    { nodeType: "table", content: [row("Status", "Limit", "Exclusions"), row("Unused & Unopened", "Other period", "Software excluded")] },
    paragraph("Keep proof of purchase.")
  ] }
} }] } });

test("routes retailer queries and dependent turns without swallowing topic changes", () => {
  assert.equal(retailerIntent("what are the jb hifi return policy"), true);
  const history = [{ question: "JB Hi-Fi returns?", answer: "not evidence" }];
  assert.equal(retailerIntent("I opened it, can I return it?", history), true);
  assert.equal(retailerIntent("Can I return it to Kmart?", history), false);
  assert.equal(retailerIntent("What does section 51 say?", history), false);
  assert.equal(retailerIntent("Can I apply to NCAT?", history), false);
});
test("keeps different product categories, row headers, and exclusions together", () => {
  const passages = policyPassages(fixture());
  assert.equal(passages.length, 5);
  assert.match(passages[3], /Media products\nStatus \| Limit \| Exclusions\nUnused & Unopened \| Other period \| Software excluded/);
});
test("live route sends no question or history and returns dated retailer citations", async () => {
  let calls = 0;
  const result = await policyAnswer("JB Hi-Fi returns?", [], { online: true, fetcher: async (url, options) => {
    calls++;
    assert.equal(url, contentURL); assert.equal(options.redirect, "error"); assert.equal(options.body, undefined);
    return Response.json(fixture());
  } });
  assert.equal(calls, 1); assert.equal(result.policy_lookup.status, "fetched");
  assert.equal(result.evidence[0].source_kind, "retailer_policy");
  assert.ok(result.evidence[0].fetched_at); assert.match(result.answer, /Marketplace/);
  assert.match(result.answer, /Software excluded/); assert.equal(result.abstained, false);
});
test("network failure and changed article schemas ask a useful question without invented terms", async () => {
  for (const fetcher of [async () => { throw Error("offline"); }, async () => Response.json({})]) {
    const result = await policyAnswer("JB Hi-Fi refunds?", [], { online: true, fetcher });
    assert.equal(result.policy_lookup.status, "unavailable"); assert.deepEqual(result.evidence, []);
    assert.match(result.answer, /faulty/); assert.doesNotMatch(result.answer, /\[1\]|30 days/i);
  }
});
test("browser demo provides the official link and states that live lookup needs the API", async () => {
  const result = await browserClient.ask("JB Hi-Fi returns?", new AbortController().signal);
  assert.equal(result.mode, "retailer-policy"); assert.equal(result.policy_lookup.status, "requires_api");
  assert.equal(result.abstained, false); assert.match(result.answer, /Connect the local API/);
  assert.deepEqual(result.evidence, []);
});
test("unrelated questions never access the retailer", async () => {
  assert.equal(await policyAnswer("What does section 51 say?", [], { online: true, fetcher: () => { throw Error("must not fetch"); } }), null);
});
