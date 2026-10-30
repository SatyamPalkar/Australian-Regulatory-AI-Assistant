"""Replay frozen conversations without fetching sources or generating legal answers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.assistant import LocalController, controller_spec
from reg_assistant.session import ConversationState
from reg_assistant.conversation import contextual_question


def intent_of(decision):
    if "intent" in decision:
        return decision["intent"]
    if decision.get("fact_group"):
        return {"MODELS":"models","TOOLS":"tools","DATA":"data","OVERVIEW":"overview"}[decision["fact_group"]]
    return {"statutory":"law","policy":"policy","chat":"greeting","clarify":"clarify","recovery":"recovery"}.get(decision["action"], "unknown")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--legacy", type=Path, help="Saved pre-fix controller module for baseline replay")
    parser.add_argument("--provider", choices=["local", "groq"], default="local")
    parser.add_argument("--request-interval", type=float, default=12, help="Seconds between Groq requests to respect free-tier limits")
    args=parser.parse_args()
    if args.provider == "groq" and (args.legacy or args.model):
        parser.error("Groq evaluation uses configs/groq.json, without --legacy or --model")
    spec=json.loads(args.model.read_text()) if args.model else controller_spec()
    if args.provider == "groq":
        from reg_assistant.groq_backend import GroqClient, GroqController
        controller = GroqController(GroqClient(request_interval=args.request_interval))
        spec = {**controller.model_spec, "configuration": controller.client.config}
    elif args.legacy:
        module_spec=importlib.util.spec_from_file_location("reg_assistant.baseline_controller",args.legacy)
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        controller=module.LocalController()
    else:
        controller=LocalController(model_spec=spec)
    # A separate process per run isolates peak allocation and loaded model memory.
    mx = None
    if args.provider == "local":
        import mlx.core as mx
        mx.reset_peak_memory()
    rows=[];wrong_tools=0;repeat_clarifications=0
    for line in args.cases.read_text().splitlines():
        conversation=json.loads(line);state=ConversationState();history=[];streak=0
        for number,case in enumerate(conversation["turns"],1):
            started=time.perf_counter()
            decision=controller.plan(case["question"],history[-3:]) if args.legacy else controller.plan(case["question"],history[-3:],state=state)
            elapsed=(time.perf_counter()-started)*1000
            if args.legacy and decision["action"] == "statutory":
                decision["search_question"] = contextual_question(case["question"],history[-3:])
            action=decision["action"];intent=intent_of(decision)
            checks={}
            if "intents" in case: checks["intent"]=intent in case["intents"]
            if "actions" in case: checks["action"]=action in case["actions"]
            if "retailer" in case and action == "policy": checks["retailer"]=decision.get("retailer", "jb_hifi" if action=="policy" else "none")==case["retailer"]
            if case.get("search_contains"): checks["search_context"]=case["search_contains"].casefold() in decision.get("search_question", "").casefold()
            wrong_tool=bool(case.get("forbid_policy") and action=="policy")
            wrong_tools+=wrong_tool
            checks["no_wrong_policy_tool"]=not wrong_tool
            streak=streak+1 if action=="clarify" else 0
            repeated=streak>1;repeat_clarifications+=repeated
            checks["no_repeated_clarification"]=not repeated
            if action=="recovery": checks["actionable_recovery"]=bool(decision.get("quick_actions"))
            rows.append({"conversation":conversation["id"],"turn":number,"question":case["question"],"passed":all(checks.values()),
                         "checks":checks,"intent":intent,"action":action,"relation":decision.get("relation"),
                         "retailer":decision.get("retailer"),"search_question":decision.get("search_question"),
                         "invalid_plan":decision.get("invalid_plan",False),"answer":decision.get("answer", ""),
                         "raw_decision":getattr(controller,"last_raw",None),"latency_ms":round(elapsed,2)})
            state.advance(case["question"], decision)
            reply=decision.get("answer") or "Fresh source evidence is required for this question."
            history.append({"question":case["question"],"answer":reply[:4000]})
            print(f"{'PASS' if all(checks.values()) else 'FAIL'} {conversation['id']}/{number}: {intent} {action}",flush=True)
    latencies=[r["latency_ms"] for r in rows]
    warm=latencies[1:] or latencies
    p95=sorted(warm)[min(len(warm)-1,int(.95*len(warm)))]
    report={"kind":"controller-only routing replay; no legal factual-support assessment", "provider":args.provider, "legacy":bool(args.legacy), "evaluation_protocol": "v2: legacy retrieval resolver credited; retailer target checked on actual policy calls",
            "cases_sha256":hashlib.sha256(args.cases.read_bytes()).hexdigest(),
            "controller_code_sha256":hashlib.sha256((args.legacy or ROOT/"reg_assistant/assistant.py").read_bytes()).hexdigest(),
            "session_code_sha256":hashlib.sha256((ROOT/"reg_assistant/session.py").read_bytes()).hexdigest(),"model":spec,"temperature":0,
            "metrics":{"turns":len(rows),"passed":sum(r["passed"] for r in rows),"accuracy":sum(r["passed"] for r in rows)/len(rows),
                       "invalid_plans":sum(r["invalid_plan"] for r in rows),"wrong_policy_tool_calls":wrong_tools,
                       "repeated_clarifications":repeat_clarifications,"warm_median_ms":statistics.median(warm),
                       "warm_p95_ms":p95,"first_turn_ms":latencies[0],"peak_mlx_gib":mx.get_peak_memory()/2**30 if mx else None,
                       "peak_rss_gib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(2**30 if sys.platform=="darwin" else 2**20)},"results":rows}
    if args.provider == "groq":
        report["provider_code_sha256"] = hashlib.sha256((ROOT/"reg_assistant/groq_backend.py").read_bytes()).hexdigest()
        report["latency_note"] = "Includes client-side request pacing; not comparable to unpaced local latency. Provider aliases are not immutable model revisions."
        controller.client.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report["metrics"],indent=2),flush=True)


if __name__=="__main__":main()
