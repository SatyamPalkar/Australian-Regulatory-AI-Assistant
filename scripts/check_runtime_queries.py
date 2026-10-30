"""Development smoke checks with the real controller; not a held-out benchmark."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.assistant import LocalController


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "eval/controller-runtime-dev.jsonl")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    controller, rows = LocalController(), []
    for line in args.cases.read_text().splitlines():
        case = json.loads(line)
        start = time.perf_counter()
        result = controller.plan(case["question"], case.get("history"))
        has_facts = "runtime_facts" in result
        passed = has_facts == case["runtime"] and (not case.get("groups") or result.get("fact_group") in case["groups"])
        rows.append({"id": case["id"], "question": case["question"], "passed": passed,
                     "action": result["action"], "runtime_facts_used": has_facts, "fact_group": result.get("fact_group"),
                     "answer": result["answer"], "latency_ms": round((time.perf_counter() - start) * 1000, 2)})
        print(f"{'PASS' if passed else 'FAIL'} {case['id']} · {result.get('fact_group') or result['action']}", flush=True)
    passed = sum(row["passed"] for row in rows)
    report = {"kind": "development smoke check, not held-out evaluation", "model": controller.model_spec,
              "adapter": False, "questions": len(rows), "passed": passed, "results": rows}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"{passed}/{len(rows)} development cases passed")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
