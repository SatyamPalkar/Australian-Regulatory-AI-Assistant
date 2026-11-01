"""Real CPU embedding regression and process-memory check; no hosted model calls."""
import argparse
import json
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reg_assistant.core import read_jsonl
from reg_assistant.semantic_cpu import ROOT, load_semantic_cpu_pipeline, configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/semantic-cpu-dev.json")
    args = parser.parse_args()
    pipeline = load_semantic_cpu_pipeline(None)
    rows, latencies = [], []
    for filename in ("consumer-law-dev.jsonl", "product-warranty-dev.jsonl"):
        for row in read_jsonl(ROOT / "eval" / filename):
            started = time.perf_counter()
            result = pipeline.ask(row["question"])
            latencies.append((time.perf_counter() - started) * 1000)
            ids = {hit["id"] for hit in result["evidence"]}
            passed = bool(ids.intersection(row["expected_sources"])) if row["answerable"] else not ids
            rows.append({"suite": filename, "id": row["id"], "passed": passed,
                         "expected_sources": row["expected_sources"], "retrieved_sources": sorted(ids)})
    heavy = sorted({"torch", "mlx", "transformers", "sentence_transformers"}.intersection(sys.modules))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
    report = {"kind": "Observed development retrieval regression; not held-out accuracy or factual-answer evaluation",
              "platform": platform.platform(), "embedding": configuration(), "reranker": None,
              "cases": len(rows), "passed": sum(row["passed"] for row in rows),
              "median_retrieval_ms": round(statistics.median(latencies), 2),
              "peak_process_rss_mib": round(peak, 2), "heavy_imports": heavy,
              "memory_limit_note": "Local process RSS is not a measurement of Render's Linux container memory.",
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Retrieval development checks: {report['passed']}/{len(rows)}; peak RSS {peak:.1f} MiB; median {report['median_retrieval_ms']} ms")
    return 0 if report["passed"] == len(rows) and not heavy else 1


if __name__ == "__main__":
    raise SystemExit(main())
