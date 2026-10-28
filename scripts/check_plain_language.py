"""Observed-user development regressions for source-linked plain-language follow-ups."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import read_jsonl, write_json
from reg_assistant.rag import load_pipeline


def main():
    pipeline = load_pipeline(adapter=str(ROOT / "adapters/consumer-law"))
    title = {"question": "What does the supplier guarantee about the right to sell goods?", "answer": "The supplier guarantees a right to dispose of the property in the goods when ownership passes. [1]"}
    typo = "i still want to undersatnd it but in normal language sumarise it for mr"
    cases = [
        ("reported-typos", typo, [title], "acl-s51"),
        ("plain-english", "Can you summarise it in plain English?", [title], "acl-s51"),
        ("failed-retry", "Explain that in simple words", [title, {"question": typo, "answer": "No evidence."}], "acl-s51"),
        ("after-exceptions", "Summarise it please", [title, {"question": "What are the exceptions?", "answer": "Read the source."}], "acl-s51"),
        ("warranties", "Can you summarise it in plain English?", [{"question": "what are the warranties on electronics products", "answer": "Warranties. [1]"}], "acl-s59"),
        ("new-visa-topic", "Summarise my visa renewal requirements", [title], None),
        ("new-fee-request", "Summarise it and tell me the current NCAT filing fee", [title], None),
        ("missing-brand-policy", "summarise it", [{"question": "What is Apple's current manufacturer warranty period for a MacBook?", "answer": "I cannot answer."}], None),
    ]
    results = []
    for name, question, history, expected in cases:
        result = pipeline.ask(question, history)
        passed = (not result["abstained"] and result["mode"] == "plain-language" and result["evidence"][0]["id"] == expected) if expected else result["abstained"]
        results.append({"id": name, "question": question, "history": history, "expected_source": expected, **result, "regression_pass": bool(passed)})
        print(f"{name}: {'PASS' if passed else 'FAIL'} | {result['answer']}", flush=True)
    write_json(ROOT / "reports/plain-language-regression.json", {
        "purpose": "Observed-user development regressions, not an independent legal-accuracy benchmark. Prepared guides are project-authored, not LoRA outputs.",
        "guides_sha256": hashlib.sha256((ROOT / "data/plain_language_guides.json").read_bytes()).hexdigest(),
        "threshold_unchanged": .5, "passed": sum(r["regression_pass"] for r in results), "questions": len(results), "results": results})
    return 0 if all(r["regression_pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
