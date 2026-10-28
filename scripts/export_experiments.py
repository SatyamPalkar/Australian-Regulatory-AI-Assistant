"""Publish measured experiment summaries, checking their frozen inputs first."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = ["tfidf", "hybrid", "base-rag", "adapter-rag"]


def main():
    split = json.loads((ROOT / "eval/split-manifest.json").read_text())
    for name, digest in split["files"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen input differs: {name}")
    runs = []
    for mode in MODES:
        file = f"reports/test-{mode}.json"
        report = json.loads((ROOT / file).read_text())
        if (report["questions_sha256"] != split["files"]["eval/benchmark-v1.jsonl"]
                or report["corpus_sha256"] != split["corpus_sha256"]
                or report["metrics"]["questions"] != 36 or len(report["results"]) != 36
                or report["mode"] != mode or report["suite"] != "test"):
            raise ValueError(f"Mismatched experiment inputs: {file}")
        if report["metrics"]["factual_correctness"] is not None or report["metrics"]["citation_entailment"] is not None:
            raise ValueError("Human accuracy must not be inferred from automated checks")
        runs.append({"mode": mode, "metrics": report["metrics"], "report": file})
    output = {"runs": runs, "questions_sha256": split["files"]["eval/benchmark-v1.jsonl"],
              "corpus_sha256": split["corpus_sha256"],
              "limitations": "Synthetic section-disjoint questions. Source and citation checks do not measure factual correctness. Human factual/entailment review pending. End-to-end latency on one M3 Pro; first request includes cold loading."}
    (ROOT / "site/lib/experiments.json").write_text(json.dumps(output, indent=2) + "\n")
    lines = ["# Frozen experiment comparison", "", output["limitations"], "",
             "| Pipeline | Source top 1 | Source top 3 | Supported answered | Unsupported declined | Median latency | Peak MLX |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for run in runs:
        m = run["metrics"]
        perc = lambda k: f"{100*m[k]:.1f}%"
        lines.append(f"| [{run['mode']}]({Path(run['report']).name}) | {perc('retrieval_hit_at_1')} | {perc('retrieval_hit_at_3')} | {perc('answerable_response_rate')} | {perc('unsupported_abstention_rate')} | {m['p50_latency_ms']/1000:.3f} s | {m['peak_mlx_memory_gb']:.2f} GB |")
    lines += ["", "24 supported questions; 12 unsupported questions. Retrieval examines three chunks. The RAG evidence pack deduplicates sections and expands short provisions to their full text.",
              "", "Extractive pipelines return passages without establishing answerability. A model response is accepted only when each paragraph ends in valid source references; rejected raw generations remain in the reports for inspection.",
              "", "All generation uses the same prompt, retrieval settings and greedy decoding. The adapter ran 60 steps on 28 synthetic training examples. Selection of the local adapter was based on development behavior before the test comparison, not on test accuracy.",
              "", "Latency includes CPU retrieval/reranking and MLX generation. Peak MLX allocation excludes CPU models and other applications. Cold first requests are marked in each report. Human review CSV files are intentionally ungraded.",
              "", "Re-run commands and limitations are in [EXPERIMENTS.md](../EXPERIMENTS.md).", ""]
    (ROOT / "reports/comparison.md").write_text("\n".join(lines))
    print("Verified and exported four measured runs.")


if __name__ == "__main__":
    main()
