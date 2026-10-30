"""Opt-in live API smoke test. Uses synthetic questions, never reads an API key."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, default=Path("reports/groq-app-smoke.json"))
    parser.add_argument("--pause", type=float, default=20)
    args = parser.parse_args()

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(args.origin.rstrip("/") + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=150) as response:
            return json.load(response)

    status = request("/api/status")
    if status.get("inference_provider") != "groq":
        raise SystemExit("Expected a Groq-backed server; no questions sent.")
    cases = [
        ("Which models power this assistant?", "chat", None, "conversation"),
        ("What does the supplier guarantee about the right to sell goods?", "statutory", "acl-s51", "rag"),
        ("i still want to undersatnd it but in normal language sumarise it for mr", "statutory", "acl-s51", "plain-language"),
        ("Which models are you using?", "chat", None, "conversation"),
        ("What is the current NCAT application fee in Sydney?", "statutory", None, "abstention"),
        ("What are JB Hi-Fi's return terms?", "policy", None, "retailer-policy"),
        ("What does section 54 say about acceptable quality?", "statutory", "acl-s54", "rag"),
    ]
    history, session, rows = [], None, []
    for number, (question, action, source, mode) in enumerate(cases):
        if number:
            time.sleep(args.pause)
        body = {"question": question, "history": history[-3:]}
        if session:
            body["conversation_id"] = session
        try:
            result = request("/api/ask", body)
        except (urllib.error.URLError, TimeoutError):
            rows.append({"question": question, "passed": False, "error": "API request failed; no response body logged"})
            break
        session = result["conversation_id"]
        trace = result["trace"]
        checks = {"provider": trace.get("inference_provider") == "groq",
                  "route": trace.get("controller_action", trace.get("response_strategy")) == action
                           or action == "chat" and result.get("mode") == "conversation",
                  "citation_structure": result.get("citation_format_valid", True),
                  "mode": result["abstained"] if mode == "abstention" else result.get("mode") == mode,
                  "no_lora": not trace.get("adapter", False)}
        if source:
            checks["expected_evidence"] = source in {s["id"] for s in result["evidence"]}
        if mode == "rag":
            checks["hosted_generation"] = trace.get("generator") == status["models"]["generator"]["repository"]
        if mode == "retailer-policy":
            checks["official_policy_fetched"] = result.get("policy_lookup", {}).get("status") == "fetched"
        rows.append({"question": question, "passed": all(checks.values()), "checks": checks,
                     "answer": result["answer"], "mode": result["mode"], "abstained": result["abstained"],
                     "sources": [{"id": s["id"], "url": s["url"]} for s in result["evidence"]], "trace": trace})
        history.append({"question": question, "answer": result["answer"][:4000]})
        print(f"{'PASS' if all(checks.values()) else 'FAIL'} live API case {number + 1}/{len(cases)}", flush=True)
    passed = sum(r["passed"] for r in rows)
    report = {"kind": "live Groq API integration smoke; structural checks and expected source presence, not independent factual verification",
              "model": status["models"]["generator"], "expected_cases": len(cases), "passed": passed,
              "complete": len(rows) == len(cases), "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Live integration: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
