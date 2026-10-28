import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from .core import (EMBEDDING_MODEL, LLM_MODEL, MLXGenerator, Retriever, answer,
                   build_index, citation_numbers, read_jsonl, write_json)
from .ingest import ingest


def model_options(parser):
    parser.add_argument("--index", default="data/index.json")
    parser.add_argument("--generator", choices=["extractive", "mlx"], default="extractive")
    parser.add_argument("--model", default=LLM_MODEL)
    parser.add_argument("--adapter", help="MLX adapter folder for the later fine-tuned comparison")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, help="Retrieval threshold; tune only on development data")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Australian regulatory guidance prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("ingest", help="Download official HTML sources; requires network")
    fetch.add_argument("--manifest", default="data/sources.json")
    fetch.add_argument("--output", default="data/documents.jsonl")
    fetch.add_argument("--raw-dir", default="data/raw")
    index = sub.add_parser("index", help="Build a local lexical or semantic index")
    index.add_argument("--documents", default="data/consumer_law.jsonl")
    index.add_argument("--output", default="data/index.json")
    index.add_argument("--backend", choices=["tfidf", "semantic"], default="tfidf")
    index.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--json", action="store_true")
    model_options(ask)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--questions", default="eval/consumer-law-dev.jsonl")
    evaluate.add_argument("--output", default="reports/consumer-law-baseline.json")
    model_options(evaluate)
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            count = ingest(args.manifest, args.output, args.raw_dir)
            print(f"Saved {count} official pages to {args.output}")
            return 0
        if args.command == "index":
            data = build_index(read_jsonl(args.documents), args.backend, args.embedding_model)
            write_json(args.output, data)
            print(f"Indexed {len(data['chunks'])} chunks with {args.backend} into {args.output}")
            return 0
        if args.adapter and args.generator != "mlx":
            raise ValueError("--adapter requires --generator mlx")
        if args.top_k < 1:
            raise ValueError("--top-k must be positive")
        if args.min_score is not None and not 0 <= args.min_score <= 1:
            raise ValueError("--min-score must be between 0 and 1")
        index_bytes = Path(args.index).read_bytes()
        retriever = Retriever(json.loads(index_bytes))
        generator = MLXGenerator(args.model, args.adapter) if args.generator == "mlx" else None

        def run(question):
            return answer(question, retriever, generator, args.top_k, args.min_score)

        if args.command == "ask":
            result = run(args.question)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result["answer"])
                if result["evidence"] and not result["abstained"]:
                    print("\nSources:")
                    for i, source in enumerate(result["evidence"], 1):
                        date = source.get("version_date", source.get("retrieved_at", source.get("verified_on", "unknown")))
                        print(f"[{i}] {source['title']} — {source['url']}")
                        print(f"    {source['source_kind']}; source date: {date}; chunk: {source['chunk_id']}")
            return 0
        questions = read_jsonl(args.questions)
        if not questions:
            raise ValueError("Evaluation requires at least one question")
        rows = []
        for row in questions:
            start = time.perf_counter()
            result = run(row["question"])
            elapsed = time.perf_counter() - start
            retrieved_ids = {hit["id"] for hit in result["retrieved"]}
            citations = citation_numbers(result["answer"])
            cited_ids = {result["evidence"][i - 1]["id"] for i in citations
                         if 1 <= i <= len(result["evidence"])}
            rows.append({**row, **result, "latency_seconds": elapsed,
                         "retrieval_hit_at_1": bool(result["retrieved"] and result["retrieved"][0]["id"] in row["expected_sources"]) if row["answerable"] else None,
                         "retrieval_hit": bool(set(row["expected_sources"]) & retrieved_ids) if row["answerable"] else None,
                         "expected_source_cited": bool(set(row["expected_sources"]) & cited_ids) if row["answerable"] else None,
                         "abstention_correct": result["abstained"] == (not row["answerable"]),
                         "keyword_coverage": sum(term.lower() in result["answer"].lower() for term in row["expected_terms"]) / len(row["expected_terms"]) if row["expected_terms"] else None})
        positives = [row for row in rows if row["answerable"]]
        negatives = [row for row in rows if not row["answerable"]]
        def mean(values):
            return sum(values) / len(values) if values else None
        metrics = {"questions": len(rows), "retrieval_hit_at_1": mean([r["retrieval_hit_at_1"] for r in positives]),
                   "retrieval_hit_at_k": mean([r["retrieval_hit"] for r in positives]),
                   "expected_source_cited_rate": mean([r["expected_source_cited"] for r in positives]),
                   "unsupported_abstention_rate": mean([r["abstained"] for r in negatives]),
                   "answerable_response_rate": mean([not r["abstained"] for r in positives]),
                   "citation_format_pass_rate": mean([r["citation_format_valid"] for r in rows]),
                   "mean_latency_seconds": mean([r["latency_seconds"] for r in rows])}
        report = {"configuration": vars(args), "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
                  "questions_sha256": hashlib.sha256(Path(args.questions).read_bytes()).hexdigest(),
                  "corpus_sha256": retriever.index["corpus_sha256"],
                  "limitations": "Development set only. Reference syntax, source presence and keywords do not measure factual correctness or entailment. Extractive mode does not judge answerability. Latency includes cold loading on the first applicable question.",
                  "metrics": metrics, "results": rows}
        write_json(args.output, report)
        print(json.dumps(metrics, indent=2))
        print(f"Full report: {args.output}")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
