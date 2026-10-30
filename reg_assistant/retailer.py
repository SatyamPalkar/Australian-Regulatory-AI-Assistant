"""Official retailer context, isolated from the versioned statutory RAG corpus.

Only the fixed public content endpoint used by JB Hi-Fi's help centre is fetched.
No user question, conversation, credentials or model prompt is sent to the retailer.
"""
import json
import re
import time
from datetime import datetime, timezone
from urllib.request import HTTPRedirectHandler, Request, build_opener

POLICY_URL = "https://www.jbhifi.com.au/pages/help-and-support/360053005194-refunds-warrant"
CONTENT_URL = ("https://themeapis.jbhifi.com.au/content/entries?content_type=supportArticle"
               "&fields.legacyId=360053005194&include=6&shouldUsePreviewSpace=false")
MAX_BYTES = 2_000_000
BRAND = re.compile(r"\bjb[\s-]*hi[\s-]*fi\b|\bjbhifi\b", re.I)
TOPIC = re.compile(r"\b(return\w*|refund\w*|warrant\w*|exchange\w*|fault\w*|broken|change of mind)\b", re.I)
FOLLOWUP = re.compile(r"^(?:and\b|what if\b|what about\b|can i\b|does (?:that|it)\b|explain\b|summari[sz]e\b|it\b|yes\b|no\b|i (?:bought|opened|have|changed)\b)", re.I)


def retailer_intent(question, history=()):
    if BRAND.search(question):
        return bool(TOPIC.search(question))
    # Carry the retailer forward only for short dependent turns, never a new topic.
    if (history and len(question) < 300 and FOLLOWUP.search(question.strip())
            and not re.search(r"\b(kmart|amazon|officeworks|harvey norman|ncat|bunnings)\b", question, re.I)
            and (TOPIC.search(question) or re.search(r"\b(it|that|this|opened|bought|summari[sz]e|explain|yes|no)\b", question, re.I))):
        previous = history[-1]["question"]
        return retailer_intent(previous, history[:-1])
    return False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Policy endpoint redirected; its new location must be reviewed")


def fetch_policy():
    request = Request(CONTENT_URL, headers={"User-Agent": "Mozilla/5.0 RegulatoryResearch/0.3",
                                          "Accept": "application/json"})
    with build_opener(NoRedirect).open(request, timeout=8) as response:
        if "application/json" not in response.headers.get("Content-Type", ""):
            raise ValueError("The policy endpoint did not return article data")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Policy response exceeded size limit")
    return json.loads(raw)


def node_text(node):
    if node.get("nodeType") == "text":
        return node.get("value", "")
    separator = " | " if node.get("nodeType") == "table-row" else " "
    return separator.join(filter(None, (node_text(n).strip() for n in node.get("content", []))))


def policy_passages(payload):
    """Keep paragraph and table-row boundaries, including headers and category labels."""
    items = payload.get("data", {}).get("items", [])
    if len(items) != 1 or str(items[0].get("fields", {}).get("legacyId")) != "360053005194":
        raise ValueError("Unexpected official article")
    fields = items[0]["fields"]
    if fields.get("heading") != "Refunds & Warranties guide":
        raise ValueError("Official article title changed")
    nodes = fields.get("mainBody", {}).get("content", [])
    passages, heading = [], fields["heading"]
    for node in nodes:
        kind = node.get("nodeType", "")
        if kind.startswith("heading"):
            heading = node_text(node)
        elif kind == "table":
            rows = node.get("content", [])
            headers = node_text(rows[0]) if rows else ""
            for row in rows[1:]:
                value = node_text(row)
                if value.strip():
                    passages.append(f"{heading}\n{headers}\n{value}")
        elif kind == "paragraph":
            value = node_text(node).strip()
            if value:
                passages.append(value)
    # Fail closed on empty pages, schema drift or incomplete policy data.
    required = ["This Guide applies", "Our goods come with guarantees", "proof of purchase"]
    selected = [next((p for p in passages if term.casefold() in p.casefold()), "") for term in required]
    change_of_mind = [p for p in passages if "unused & unopened" in p.casefold()]
    if not all(selected) or not change_of_mind or any(p.count("\n") != 2 for p in change_of_mind):
        raise ValueError("Required policy context is missing")
    return selected[:2] + change_of_mind + selected[2:]


def answer_policy(question, history=(), fetcher=None, *, routed=False):
    """Return None for statutory questions; policy quotes never go through the LLM."""
    if not routed and not retailer_intent(question, history):
        return None
    start = time.perf_counter()
    evidence = []
    lookup_status = "unavailable"
    try:
        passages = policy_passages((fetcher or fetch_policy)())
        fetched = datetime.now(timezone.utc).isoformat()
        for i, passage in enumerate(passages):
            evidence.append({"id": f"jb-policy-{i}", "chunk_id": f"jb-policy-{i}",
                             "title": "JB Hi-Fi — Refunds & Warranties guide",
                             "url": POLICY_URL, "publisher": "JB Hi-Fi", "jurisdiction": "Australia",
                             "source_kind": "retailer_policy", "fetched_at": fetched,
                             "content_url": CONTENT_URL, "text": passage, "evidence_span": "policy_excerpt"})
        # Short, source-derived context; retain full passages in the evidence cards.
        coverage = " ".join(re.split(r"(?<=[.!?])\s+", passages[0])[:2])
        summaries = [f"Who this covers: {coverage} [1]", f"Faulty products: {passages[1]} [2]"]
        for i, passage in enumerate(passages[2:-1], 3):
            heading, _headers, row = passage.split("\n", 2)
            summaries.append(f"Change of mind — {heading}: {row} [{i}]")
        proof = next(sentence for sentence in re.split(r"(?<=[.!?])\s+", passages[-1]) if "proof of purchase" in sentence.casefold())
        summaries.append(f"Starting a return: {proof} [{len(passages)}]")
        answer = "JB Hi-Fi treats faulty products and change-of-mind returns differently. Here is the relevant policy context.\n\n" + "\n\n".join(summaries)
        lookup_status = "fetched"
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        answer = ("I recognise this as a JB Hi-Fi returns-policy question, but I couldn’t verify the official policy text just now. "
                  "I can’t confirm a return deadline or whether your purchase qualifies. "
                  "Use the official policy link below to check the current terms.")
    answer += ("\n\nIs the item faulty, or have you changed your mind? What product is it, when did you buy it, "
               "has it been opened, and was the seller JB Hi-Fi directly or a Marketplace seller?")
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    return {"answer": answer, "evidence": evidence, "retrieved": evidence, "abstained": False,
            "mode": "retailer-policy", "latency_ms": elapsed,
            "scope_note": "Retailer policy lookup. These excerpts are retailer guidance, not a statutory source or an individual eligibility decision.",
            "policy_lookup": {"status": lookup_status, "url": POLICY_URL, "retailer": "JB Hi-Fi"},
            "trace": {"retrieval_ms": elapsed, "response_strategy": "official_policy",
                      "generator": "None — official policy excerpts", "reranker": "Not used",
                      "history_turns_used": int(bool(history) and not BRAND.search(question))}}
