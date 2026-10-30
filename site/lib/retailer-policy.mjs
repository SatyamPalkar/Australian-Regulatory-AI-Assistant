// The official public content endpoint used by JB Hi-Fi's help centre. No query
// text or history is sent to it. Keep the frozen statutory engine independent.
export const policyURL = "https://www.jbhifi.com.au/pages/help-and-support/360053005194-refunds-warrant";
export const contentURL = "https://themeapis.jbhifi.com.au/content/entries?content_type=supportArticle&fields.legacyId=360053005194&include=6&shouldUsePreviewSpace=false";
const brand = /\bjb[\s-]*hi[\s-]*fi\b|\bjbhifi\b/i;
const topic = /\b(return\w*|refund\w*|warrant\w*|exchange\w*|fault\w*|broken|change of mind)\b/i;
const dependent = /^(?:and\b|what if\b|what about\b|can i\b|does (?:that|it)\b|explain\b|summari[sz]e\b|it\b|yes\b|no\b|i (?:bought|opened|have|changed)\b)/i;
export function retailerIntent(question, history = []) {
  if (brand.test(question)) return topic.test(question);
  const previous = history.at(-1)?.question || "";
  return question.length < 300 && dependent.test(question.trim()) && !/\b(kmart|amazon|officeworks|harvey norman|ncat|bunnings)\b/i.test(question) && (topic.test(question) || /\b(it|that|this|opened|bought|summari[sz]e|explain|yes|no)\b/i.test(question)) && retailerIntent(previous, history.slice(0, -1));
}
function nodeText(node) {
  if (node.nodeType === "text") return node.value || "";
  return (node.content || []).map(nodeText).map(v => v.trim()).filter(Boolean).join(node.nodeType === "table-row" ? " | " : " ");
}
export function policyPassages(payload) {
  const items = payload?.data?.items || [];
  if (items.length !== 1 || String(items[0].fields?.legacyId) !== "360053005194" || items[0].fields.heading !== "Refunds & Warranties guide") throw Error("Unexpected official article");
  const passages = [];
  let heading = items[0].fields.heading;
  for (const node of items[0].fields.mainBody?.content || []) {
    if (node.nodeType?.startsWith("heading")) heading = nodeText(node);
    else if (node.nodeType === "table") {
      const [headers, ...rows] = node.content || [];
      for (const row of rows) if (nodeText(row).trim()) passages.push(`${heading}\n${nodeText(headers)}\n${nodeText(row)}`);
    } else if (node.nodeType === "paragraph" && nodeText(node).trim()) passages.push(nodeText(node).trim());
  }
  const selected = ["This Guide applies", "Our goods come with guarantees", "proof of purchase"].map(term => passages.find(p => p.toLowerCase().includes(term.toLowerCase())));
  const changeOfMind = passages.filter(p => p.toLowerCase().includes("unused & unopened"));
  if (selected.some(p => !p) || !changeOfMind.length || changeOfMind.some(p => p.split("\n").length !== 3)) throw Error("Required policy context is missing");
  return [...selected.slice(0, 2), ...changeOfMind, ...selected.slice(2)];
}
export async function policyAnswer(question, history = [], { online = false, fetcher = fetch } = {}) {
  if (!retailerIntent(question, history)) return null;
  const start = performance.now();
  let evidence = [], lookupStatus = online ? "unavailable" : "requires_api";
  let answer = online
    ? "I recognise this as a JB Hi-Fi returns-policy question, but I couldn’t verify the official policy text just now. I can’t confirm a return deadline or whether your purchase qualifies. Use the official policy link below to check the current terms."
    : "This question needs JB Hi-Fi’s own returns policy. Browser-only mode cannot retrieve that policy because the retailer restricts cross-origin requests. Connect the local API using the connection settings for an official policy lookup, or open the official policy link below. I can’t confirm a return deadline or eligibility from the statutory collection alone.";
  if (online) try {
    const response = await fetcher(contentURL, { signal: AbortSignal.timeout(8000), redirect: "error", headers: { Accept: "application/json" } });
    if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw Error("Policy content unavailable");
    // Bound the stream before parsing, including servers without Content-Length.
    const reader = response.body.getReader();
    const chunks = []; let size = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 2000000) throw Error("Policy response too large");
        chunks.push(value);
      }
    } finally { await reader.cancel(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const passages = policyPassages(JSON.parse(new TextDecoder().decode(bytes)));
    const fetched = new Date().toISOString();
    evidence = passages.map((text, i) => ({ id: `jb-policy-${i}`, chunk_id: `jb-policy-${i}`, title: "JB Hi-Fi — Refunds & Warranties guide", url: policyURL, publisher: "JB Hi-Fi", jurisdiction: "Australia", source_kind: "retailer_policy", fetched_at: fetched, content_url: contentURL, text, evidence_span: "policy_excerpt" }));
    const coverage = passages[0].split(/(?<=[.!?])\s+/).slice(0, 2).join(" ");
    const summaries = [`Who this covers: ${coverage} [1]`, `Faulty products: ${passages[1]} [2]`];
    passages.slice(2, -1).forEach((passage, i) => {
      const [heading, , row] = passage.split("\n");
      summaries.push(`Change of mind — ${heading}: ${row} [${i + 3}]`);
    });
    const proof = passages.at(-1).split(/(?<=[.!?])\s+/).find(sentence => sentence.toLowerCase().includes("proof of purchase"));
    summaries.push(`Starting a return: ${proof} [${passages.length}]`);
    answer = "JB Hi-Fi treats faulty products and change-of-mind returns differently. Here is the relevant policy context.\n\n" + summaries.join("\n\n");
    lookupStatus = "fetched";
  } catch { /* Keep the useful clarification and official link; never invent terms. */ }
  answer += "\n\nIs the item faulty, or have you changed your mind? What product is it, when did you buy it, has it been opened, and was the seller JB Hi-Fi directly or a Marketplace seller?";
  const elapsed = Math.round((performance.now() - start) * 100) / 100;
  return { answer, evidence, retrieved: evidence, abstained: false, mode: "retailer-policy", latency_ms: elapsed,
    scope_note: "Retailer policy lookup. These excerpts are retailer guidance, not a statutory source or an individual eligibility decision.",
    policy_lookup: { status: lookupStatus, url: policyURL, retailer: "JB Hi-Fi" },
    trace: { retrieval_ms: elapsed, response_strategy: "official_policy", generator: "None — official policy excerpts", reranker: "Not used", history_turns_used: Number(Boolean(history.length) && !brand.test(question)) } };
}
