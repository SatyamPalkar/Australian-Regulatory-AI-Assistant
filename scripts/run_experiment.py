"""Reproducible comparison; reference checks are explicitly not factual accuracy."""
import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import Retriever, answer, build_index, citation_numbers, read_jsonl, write_json
from reg_assistant.rag import (HybridRetriever, MeasuredMLXGenerator, RAGPipeline,
                               model_manifest)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_split():
    manifest = json.loads((ROOT / "eval/split-manifest.json").read_text())
    for file, expected in manifest["files"].items():
        if sha(ROOT / file) != expected:
            raise ValueError(f"Frozen split was modified: {file}")
    corpus = hashlib.sha256(json.dumps(read_jsonl(ROOT / "data/consumer_law.jsonl"), sort_keys=True).encode()).hexdigest()
    if corpus != manifest["corpus_sha256"]:
        raise ValueError("Corpus changed since split was frozen")
    return manifest


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def metrics(rows):
    supported = [r for r in rows if r["answerable"]]
    unsupported = [r for r in rows if not r["answerable"]]
    latencies = sorted(r["latency_ms"] for r in rows)
    return {"questions": len(rows), "supported_questions": len(supported),
            "unsupported_questions": len(unsupported),
            "retrieval_hit_at_1": mean([r["retrieval_hit_at_1"] for r in supported]),
            "retrieval_hit_at_3": mean([r["retrieval_hit_at_3"] for r in supported]),
            "mean_reciprocal_rank": mean([r["reciprocal_rank"] for r in supported]),
            "expected_source_cited_rate": mean([r["expected_source_cited"] for r in supported]),
            "answerable_response_rate": mean([not r["abstained"] for r in supported]),
            "unsupported_abstention_rate": mean([r["abstained"] for r in unsupported]),
            "reference_keyword_coverage": mean([r["keyword_coverage"] for r in supported]),
            "citation_format_pass_rate": mean([r["citation_format_valid"] for r in rows]),
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": latencies[max(0, int(len(latencies) * .95 + .999) - 1)],
            "peak_mlx_memory_gb": max([r.get("trace", {}).get("peak_mlx_memory_gb", 0) for r in rows]),
            "factual_correctness": None, "citation_entailment": None}


def evaluate(mode, questions, hybrid_index, lexical_index, adapter):
    if mode == "tfidf":
        retriever = Retriever(lexical_index)
        def run(q):
            start = time.perf_counter()
            result = answer(q, retriever)
            result["latency_ms"] = (time.perf_counter() - start) * 1000
            return result
    else:
        generator = None if mode == "hybrid" else MeasuredMLXGenerator(adapter if mode == "adapter-rag" else None)
        pipeline = RAGPipeline(HybridRetriever(hybrid_index), generator)
        run = pipeline.ask
    rows = []
    for i, q in enumerate(questions):
        result = run(q["question"])
        ids = [h["id"] for h in result["retrieved"]]
        ranks = [rank for rank, source in enumerate(ids, 1) if source in q["expected_sources"]]
        cited = {result["evidence"][n - 1]["id"] for n in citation_numbers(result["answer"])
                 if 1 <= n <= len(result["evidence"])}
        rows.append({**q, **result, "cold_request": i == 0,
                     "retrieval_hit_at_1": bool(ranks and ranks[0] == 1) if q["answerable"] else None,
                     "retrieval_hit_at_3": bool(ranks) if q["answerable"] else None,
                     "reciprocal_rank": 1 / ranks[0] if ranks else 0 if q["answerable"] else None,
                     "expected_source_cited": bool(cited & set(q["expected_sources"])) if q["answerable"] else None,
                     "keyword_coverage": mean([t.lower() in result["answer"].lower() for t in q["expected_terms"]]),
                     "human_factual_correctness": None, "human_citation_entailment": None})
        print(f"{mode}: {i+1}/{len(questions)} {q['id']}: {'declined' if result['abstained'] else 'answered'} {result['latency_ms']:.0f}ms", flush=True)
    if mode != "tfidf":
        del pipeline
        import gc
        gc.collect()
        if mode not in ("hybrid",):
            import mlx.core as mx
            mx.clear_cache()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["dev", "test"], default="test")
    parser.add_argument("--modes", nargs="+", choices=["tfidf", "hybrid", "base-rag", "adapter-rag"],
                        default=["tfidf", "hybrid", "base-rag"])
    parser.add_argument("--adapter", default="adapters/consumer-law")
    args = parser.parse_args()
    split = verify_split()
    if "adapter-rag" in args.modes and not (ROOT / args.adapter / "adapters.safetensors").exists():
        raise ValueError("Train the adapter before comparing it")
    questions_path = ROOT / ("eval/benchmark-v1.jsonl" if args.suite == "test" else "eval/consumer-law-dev.jsonl")
    questions = read_jsonl(questions_path)
    hybrid_index = json.loads((ROOT / "data/index-hybrid.json").read_text())
    lexical_index = build_index(read_jsonl(ROOT / "data/consumer_law.jsonl"))
    for mode in args.modes:
        start = time.perf_counter()
        rows = evaluate(mode, questions, hybrid_index, lexical_index, str(ROOT / args.adapter))
        report = {"schema_version": 1, "mode": mode, "suite": args.suite,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "questions_sha256": sha(questions_path), "corpus_sha256": hybrid_index["corpus_sha256"],
                  "index_sha256": sha(ROOT / "data/index-hybrid.json"),
                  "model_manifest": model_manifest(),
                  "configuration": {"top_k": 3, "candidate_count": 12, "rrf_constant": 60,
                                    "min_reranker_probability": .5, "temperature": 0, "max_tokens": 256},
                  "adapter_sha256": sha(ROOT / args.adapter / "adapters.safetensors") if mode == "adapter-rag" else None,
                  "hardware": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
                  "wall_seconds": time.perf_counter() - start,
                  "limitations": "Synthetic section-disjoint test, not an independent legal accuracy benchmark. Keyword/source/format checks do not establish correctness or entailment. Human factual and citation-entailment review pending. First request includes cold model loading; timing is end-to-end and machine-specific.",
                  "metrics": metrics(rows), "results": rows}
        dest = ROOT / f"reports/{args.suite}-{mode}.json"
        write_json(dest, report)
        with (ROOT / f"reports/{args.suite}-{mode}-review.csv").open("w") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "question", "answer", "evidence", "factual_correctness_0_1", "citation_entailment_0_1", "notes"])
            for r in rows:
                writer.writerow([r["id"], r["question"], r["answer"], json.dumps(r["evidence"]), "", "", ""])
        print(json.dumps(report["metrics"], indent=2), flush=True)


if __name__ == "__main__":
    main()
