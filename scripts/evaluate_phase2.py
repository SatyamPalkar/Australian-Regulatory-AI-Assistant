"""Compare adapters under identical explanatory prompts and fresh contextual retrieval."""
import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import citation_numbers, read_jsonl, write_json
from reg_assistant.experiments import verify_phase2
from reg_assistant.rag import load_pipeline, model_manifest


def mean(values):
    return sum(values) / len(values) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["dev", "test"], default="dev")
    parser.add_argument("--modes", nargs="+", choices=["v1-explain", "v2-explain"], default=["v1-explain", "v2-explain"])
    args = parser.parse_args()
    manifest = verify_phase2()
    questions_path = ROOT / f"eval/phase2-{args.suite}.jsonl"
    questions = read_jsonl(questions_path)
    for mode in args.modes:
        relative_adapter = "adapters/consumer-law" if mode == "v1-explain" else "adapters/explanatory-v2-selected"
        adapter = ROOT / relative_adapter
        pipeline = load_pipeline(adapter=str(adapter), answer_style="explain")
        rows = []
        for i, q in enumerate(questions):
            result = pipeline.ask(q["question"], history=q.get("history"))
            cited = {result["evidence"][n-1]["id"] for n in citation_numbers(result["answer"])
                     if 1 <= n <= len(result["evidence"])}
            source_hit = bool(set(q["expected_sources"]) & cited) if q["answerable"] else None
            structured = (not result["abstained"] and result["citation_format_valid"]
                          and all(f"{label}:" in result["answer"] for label in ["Rule", "Meaning", "Limits"]))
            terms = q.get("qualification_terms", [])
            term_coverage = mean([term.lower() in result["answer"].lower() for term in terms])
            row = {**q, **result, "cold_request": i == 0, "expected_source_cited": source_hit,
                   "structured_explanation": bool(structured), "qualification_term_coverage": term_coverage,
                   "human_factual_correctness": None, "human_citation_entailment": None}
            rows.append(row)
            print(f"{mode} {i+1}/{len(questions)} {q['id']}: {'declined' if result['abstained'] else 'explained' if structured else 'short/unstructured'}", flush=True)
        positive = [r for r in rows if r["answerable"]]
        negative = [r for r in rows if not r["answerable"]]
        followups = [r for r in positive if r.get("history")]
        latencies = sorted(r["latency_ms"] for r in rows)
        metrics = {"questions": len(rows), "supported": len(positive), "unsupported": len(negative),
                   "supported_response_rate": mean([not r["abstained"] for r in positive]),
                   "structured_explanation_rate": mean([r["structured_explanation"] for r in positive]),
                   "expected_source_cited_rate": mean([r["expected_source_cited"] for r in positive]),
                   "qualification_term_coverage": mean([r["qualification_term_coverage"] for r in positive if r["qualification_term_coverage"] is not None]),
                   "unsupported_abstention_rate": mean([r["abstained"] for r in negative]),
                   "followup_expected_source_cited_rate": mean([r["expected_source_cited"] for r in followups]),
                   "p50_latency_ms": statistics.median(latencies),
                   "p95_latency_ms": latencies[max(0, int(len(latencies)*.95+.999)-1)],
                   "max_prompt_tokens": max(r["trace"].get("prompt_tokens", 0) for r in rows),
                   "peak_mlx_memory_gb": max(r["trace"].get("peak_mlx_memory_gb", 0) for r in rows),
                   "mean_output_tokens_supported": mean([r["trace"].get("generated_tokens", 0) for r in positive]),
                   "factual_accuracy": None, "citation_entailment": None}
        report = {"schema_version": 2, "mode": mode, "suite": args.suite,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "questions_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
                  "corpus_sha256": manifest["corpus_sha256"], "model_manifest": model_manifest(),
                  "adapter_sha256": hashlib.sha256((adapter / "adapters.safetensors").read_bytes()).hexdigest(),
                  "configuration": {"answer_style": "explain", "max_tokens": 512, "temperature": 0,
                                    "top_k": 3, "min_score": .5, "max_history_turns": 3, "history_characters": 6000},
                  "hardware": {"platform": platform.platform(), "python": platform.python_version()},
                  "metrics": metrics, "results": rows,
                  "limitations": "Synthetic source-disjoint test; related corpus topics already inspected. Qualification keywords and three labelled paragraphs are completeness/style proxies, not factual accuracy or entailment. Human review pending. Timings are single-machine, first request cold. History includes fixture answers; browser tests separately verify actual multi-turn transport."}
        destination = ROOT / f"reports/phase2-{args.suite}-{mode}.json"
        write_json(destination, report)
        with destination.with_suffix(".csv").open("w") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["id", "question", "history", "answer", "evidence", "factual_correctness_0_1", "citation_entailment_0_1", "notes"])
            for r in rows:
                writer.writerow([r["id"], r["question"], json.dumps(r.get("history", [])), r["answer"], json.dumps(r["evidence"]), "", "", ""])
        print(json.dumps(metrics, indent=2), flush=True)
        del pipeline
        import gc
        gc.collect()
        import mlx.core as mx
        mx.clear_cache()


if __name__ == "__main__":
    main()
