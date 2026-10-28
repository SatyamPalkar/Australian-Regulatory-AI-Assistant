"""Export phase-two metrics without replacing the historical v1 comparison."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.experiments import verify_phase2


def main():
    manifest = verify_phase2()
    selection = json.loads((ROOT / "reports/phase2-selection.json").read_text())
    training = json.loads((ROOT / "reports/lora-phase2.json").read_text())
    review = json.loads((ROOT / "reports/phase2-development-review.json").read_text())
    runs = []
    for mode in ["v1-explain", "v2-explain"]:
        path = f"reports/phase2-test-{mode}.json"
        report = json.loads((ROOT / path).read_text())
        if report["questions_sha256"] != manifest["files"]["eval/phase2-test.jsonl"] or report["corpus_sha256"] != manifest["corpus_sha256"]:
            raise ValueError("Phase-two report input mismatch")
        if report["metrics"]["questions"] != 16 or report["metrics"]["factual_accuracy"] is not None:
            raise ValueError("Invalid phase-two count or unreviewed accuracy claim")
        runs.append({"mode": mode, "metrics": report["metrics"], "report": path})
    summary = {"runs": runs, "serving_mode": selection["serving_mode"],
               "serving_decision": selection["serving_decision_basis"],
               "training": {k: training[k] for k in ["elapsed_seconds", "peak_mlx_memory_gb", "selected_step"]},
               "limitations": "Explanation structure and qualification-keyword scores are proxies, not factual correctness. Development source review found substantive errors; original concise adapter remains the default. New adapter is experimental. Both test and training examples are synthetic; independent review pending."}
    (ROOT / "site/lib/phase2.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Phase-two conversation and explanation experiment", "", summary["limitations"], "",
             "Both adapters use the same explanatory prompt, 512-token cap, retrieval and bounded conversation context. This isolates the adapter comparison; the production default remains the original concise profile.", "",
             "| Adapter | Supported answered | Three-part cited explanation | Qualification keyword coverage | Unsupported declined | Median latency |",
             "| --- | --- | --- | --- | --- | --- |"]
    for run in runs:
        m = run["metrics"]
        values = [f"{100*m[k]:.1f}%" for k in ["supported_response_rate", "structured_explanation_rate", "qualification_term_coverage", "unsupported_abstention_rate"]]
        lines.append(f"| [{run['mode']}]({Path(run['report']).name}) | " + " | ".join(values) + f" | {m['p50_latency_ms']/1000:.2f} s |")
    lines += ["", "10 supported and six unsupported questions. Contextual follow-ups cited the expected source for one of two supported follow-up cases in each model run. False abstentions and rejected generations are retained in the JSON reports.",
              "", "The new adapter trained on 64 source-authored examples for 120 steps; step 120 had the lowest saved-checkpoint validation loss. Validation shares source topics and targets with training. Ten training source sections are disjoint from eight test source sections. This corpus and related topics have already been inspected, so this is not an independent legal benchmark.",
              "", f"Training: {training['elapsed_seconds']:.1f} seconds, {training['peak_mlx_memory_gb']:.2f} GB peak MLX allocation. This excludes CPU model allocations and other applications.",
              "", "**Serving decision:** retain `adapters/consumer-law` with concise answers. Development proxies favored the new candidate, but a source spot-check found wrong supplier/consumer roles and misstatements of the title guarantee. See [development review](phase2-development-review.json) and [selection record](phase2-selection.json). More paragraphs do not establish better legal answers.",
              "", "Default dependent follow-ups return fresh verbatim statutory text, labelled as source wording, because live checks also found qualification errors in the original adapter. The new adapter remains available through an explicit experimental command. Human factual correctness and citation-entailment review CSV fields are blank. The original v1 benchmark files, training data and reports remain unchanged.",
              "", "See [PHASE2.md](../PHASE2.md) for reproduction, history limits and observed failures.", ""]
    (ROOT / "reports/phase2-comparison.md").write_text("\n".join(lines))
    print("Verified and exported the phase-two comparison")


if __name__ == "__main__":
    main()
