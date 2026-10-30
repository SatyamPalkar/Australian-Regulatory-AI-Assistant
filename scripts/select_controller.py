"""Select a controller only when the recorded frozen comparison meets its gates."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--check",action="store_true",help="Validate recorded selection without writing files")
    args=parser.parse_args()
    manifest=json.loads((ROOT/"eval/controller-evaluation-manifest.json").read_text())
    cases=ROOT/manifest["selection_set"]
    expected_hash=manifest["datasets"][manifest["selection_set"]]
    reports={label:json.loads((ROOT/f"reports/controller-{label}-verification-v2.json").read_text())
             for label in ["candidate","same-architecture-1.5b","before-fix"]}
    candidate=reports["candidate"];metrics=candidate["metrics"];gates=manifest["selection_gates"]
    questions=[(json.loads(line)["id"],i,t["question"]) for line in cases.read_text().splitlines()
               for i,t in enumerate(json.loads(line)["turns"],1)]
    current_code=hashlib.sha256((ROOT/"reg_assistant/assistant.py").read_bytes()).hexdigest()
    current_session=hashlib.sha256((ROOT/"reg_assistant/session.py").read_bytes()).hexdigest()
    checks={"frozen_cases_unchanged":hashlib.sha256(cases.read_bytes()).hexdigest()==expected_hash,
            "same_evaluation_protocol":len({r.get("evaluation_protocol") for r in reports.values()})==1,
            "same_cases_for_all_models":all(r["cases_sha256"]==expected_hash for r in reports.values()),
            "same_turns_for_all_models":all([(x["conversation"],x["turn"],x["question"]) for x in r["results"]]==questions for r in reports.values()),
            "current_workflow_evaluated":all(reports[k]["controller_code_sha256"]==current_code and reports[k]["session_code_sha256"]==current_session for k in ["candidate","same-architecture-1.5b"]),
            "minimum_turn_pass_rate":metrics["accuracy"]>=gates["minimum_heldout_turn_pass_rate"],
            "strictly_better_than_both_baselines":all(metrics["accuracy"]>reports[k]["metrics"]["accuracy"] for k in ["same-architecture-1.5b","before-fix"]),
            "no_wrong_policy_tools":metrics["wrong_policy_tool_calls"]==0,
            "no_repeated_clarifications":metrics["repeated_clarifications"]==0,
            "latency_within_limit":metrics["warm_p95_ms"]<=gates["warm_p95_limit_ms"],
            "mlx_memory_within_limit":metrics["peak_mlx_gib"]<=gates["peak_mlx_limit_gib"]}
    eligible=all(checks.values())
    report={"eligible":eligible,"applied":eligible and args.apply,"checks":checks,"selected_model":candidate["model"] if eligible else None,
            "comparison":{key:value["metrics"] for key,value in reports.items()},"selection_set":manifest["selection_set"],
            "cases_sha256":expected_hash,"scope":"Small routing verification set; not a legal factual-support or production-readiness assessment",
            "known_misses":[{"question":r["question"],"intent":r["intent"],"checks":r["checks"]} for r in candidate["results"] if not r["passed"]]}
    if not args.check:
        (ROOT/"reports/controller-selection.json").write_text(json.dumps(report,indent=2)+"\n")
    if eligible and args.apply:
        (ROOT/"configs/controller.json").write_text(json.dumps(candidate["model"],indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0 if eligible else 1


if __name__=="__main__":raise SystemExit(main())
