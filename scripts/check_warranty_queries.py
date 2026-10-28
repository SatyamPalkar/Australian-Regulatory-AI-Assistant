"""Real-model development regression for the reported electronics warranty failure."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import read_jsonl, write_json
from reg_assistant.rag import load_pipeline, model_manifest


def main():
    pipeline = load_pipeline(adapter=str(ROOT / "adapters/consumer-law"))
    path = ROOT / "eval/product-warranty-dev.jsonl"
    rows = []
    for example in read_jsonl(path):
        result = pipeline.ask(example["question"])
        evidence_ids = {c["id"] for c in result["evidence"]}
        passed = result["abstained"] != example["answerable"]
        if example["answerable"]:
            passed = passed and bool(evidence_ids & set(example["expected_sources"]))
            passed = passed and all(term in result["answer"].lower() for term in ["comply", "warrant"])
            # The generic statutory warranty section supplies no fixed brand warranty duration.
            passed = passed and not re.search(r"\b(?:\d+|one|two|three)\s+(?:months?|years?)\b", result["answer"], re.I)
        rows.append({**example, **result, "regression_pass": bool(passed)})
        print(f"{example['id']}: {'PASS' if passed else 'FAIL'} | {result['answer']}", flush=True)
    report = {"purpose": "Observed-user-query development regression, not a new held-out benchmark or legal accuracy measure.",
              "created_at": datetime.now(timezone.utc).isoformat(), "model_manifest": model_manifest(),
              "adapter_sha256": hashlib.sha256((ROOT / "adapters/consumer-law/adapters.safetensors").read_bytes()).hexdigest(),
              "corpus_sha256": pipeline.retriever.index["corpus_sha256"],
              "questions_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "threshold_unchanged": 0.5, "passed": sum(r["regression_pass"] for r in rows),
              "questions": len(rows), "results": rows}
    write_json(ROOT / "reports/warranty-query-regression.json", report)
    return 0 if report["passed"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
