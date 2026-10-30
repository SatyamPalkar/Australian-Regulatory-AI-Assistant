"""Validate routing fixtures without loading a model or consuming the hold-out set."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_MANIFEST = ROOT / "eval/routing-boundary/manifest.json"
ACTION = {"law":"statutory", "models":"chat", "tools":"chat", "data":"chat", "overview":"chat",
          "policy":"policy", "clarify":"clarify", "recovery":"recovery"}
RULES = {
    "consumer_law": ({"law"}, "retrieve_evidence_or_explain_coverage_limit"),
    "app_information": ({"models","tools","data","overview"}, "runtime_facts_only"),
    "retailer_policy": ({"policy"}, "official_policy_or_explicit_lookup_failure"),
    "unsupported_retailer": ({"clarify","recovery"}, "state_supported_retailer_limit"),
}


def normalise(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values(): yield from strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value: yield from strings(child)


def prompt_texts():
    from reg_assistant.assistant import SYSTEM, EXAMPLES, RELATION_SYSTEM, RELATION_EXAMPLES
    return list(strings([SYSTEM, EXAMPLES, RELATION_SYSTEM, RELATION_EXAMPLES]))


def validate_rows(splits, *, regression_questions=(), prompts=()):
    """Validate declarations; this does not assess semantic intent accuracy."""
    ids, questions, families, pairs = set(), {}, {}, {}
    regression = {normalise(q) for q in regression_questions}
    prompt_values = [normalise(p) for p in prompts]
    summary = {}
    for split, rows in splits.items():
        categories = {}
        for row in rows:
            identifier, family = row.get("id"), row.get("family")
            if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9-]+", identifier) or identifier in ids:
                raise ValueError("Missing or duplicate conversation ID")
            ids.add(identifier)
            if not isinstance(family, str) or not family.strip(): raise ValueError(f"{identifier}: missing family")
            if family in families and families[family] != split: raise ValueError(f"Scenario family crosses splits: {family}")
            families[family] = split
            turns = row.get("turns")
            if not isinstance(turns, list) or not turns: raise ValueError(f"{identifier}: empty conversation")
            if row.get("contrast_pair") and len(turns) != 1: raise ValueError("Contrast pairs must be single-turn")
            previous_questions = []
            for turn in turns:
                question, category = turn.get("question"), turn.get("category")
                if not isinstance(question, str) or not question.strip() or len(question) > 2000: raise ValueError(f"{identifier}: invalid question")
                key = normalise(question)
                if not key: raise ValueError(f"{identifier}: question has no words")
                if key in questions: raise ValueError(f"Duplicate question: {identifier} / {questions[key]}")
                if key in regression: raise ValueError(f"Existing regression question copied: {identifier}")
                if any(key in p for p in prompt_values): raise ValueError(f"Question appears in controller prompt: {identifier}")
                questions[key] = identifier
                if category not in RULES: raise ValueError(f"{identifier}: unknown category")
                allowed, expectation = RULES[category]
                intents, actions = turn.get("intents"), turn.get("actions")
                if not isinstance(intents, list) or not intents or len(set(intents)) != len(intents) or not set(intents) <= allowed:
                    raise ValueError(f"{identifier}: intent/category mismatch")
                if not isinstance(actions, list) or set(actions) != {ACTION[i] for i in intents}:
                    raise ValueError(f"{identifier}: action/intent mismatch")
                if turn.get("answer_expectation") != expectation: raise ValueError(f"{identifier}: unsupported answer expectation")
                if turn.get("forbid_policy") is not (category != "retailer_policy"): raise ValueError(f"{identifier}: incorrect policy boundary")
                if category == "retailer_policy" and turn.get("retailer") != "jb_hifi": raise ValueError(f"{identifier}: unavailable policy tool")
                if turn.get("search_contains"):
                    if category != "consumer_law" or not any(turn["search_contains"].casefold() in q.casefold() for q in previous_questions):
                        raise ValueError(f"{identifier}: search anchor is not an earlier user question")
                previous_questions.append(question)
                categories[category] = categories.get(category, 0) + 1
                if row.get("contrast_pair"):
                    pairs.setdefault(row["contrast_pair"], []).append((split, family, category))
        summary[split] = {"conversations": len(rows), "turns": sum(len(r["turns"]) for r in rows), "categories": categories}
    for pair, members in pairs.items():
        if len(members) != 2 or {m[2] for m in members} != {"consumer_law", "app_information"} or len({m[:2] for m in members}) != 1:
            raise ValueError(f"Invalid legal/app contrast pair: {pair}")
    return {"splits": summary, "contrast_pairs": len(pairs), "declared_families": len(families)}


def validate_manifest(path=DEFAULT_MANIFEST):
    path = Path(path)
    manifest = json.loads(path.read_text())
    splits = {}
    if set(manifest["files"]) != {"dev", "holdout"}: raise ValueError("Expected development and reserved hold-out splits")
    for split, spec in manifest["files"].items():
        source = path.parent / spec["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != spec["sha256"]: raise ValueError(f"Dataset hash changed: {split}")
        splits[split] = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    regression_path = path.parent / manifest["regression_set"]
    if hashlib.sha256(regression_path.read_bytes()).hexdigest() != manifest["regression_sha256"]: raise ValueError("The existing 22-turn regression set changed")
    regression = [t["question"] for row in map(json.loads, regression_path.read_text().splitlines()) for t in row["turns"]]
    result = validate_rows(splits, regression_questions=regression, prompts=prompt_texts())
    for split, summary in result["splits"].items():
        for field in ["conversations", "turns", "categories"]:
            if summary[field] != manifest["files"][split][field]: raise ValueError(f"Manifest count mismatch: {split}/{field}")
    return result


if __name__ == "__main__":
    print(json.dumps(validate_manifest(), indent=2))
