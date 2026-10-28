"""Export the Python baseline and fixtures for the deployed retrieval engine."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import MIN_QUERY_COVERAGE, STOP, Retriever, answer, build_index, read_jsonl


def main():
    output = ROOT / "site/lib"
    output.mkdir(parents=True, exist_ok=True)
    documents = read_jsonl(ROOT / "data/consumer_law.jsonl")
    manifest = json.loads((ROOT / "data/huggingface_sources.json").read_text())
    index = build_index(documents)
    index.pop("created_at")
    index["stop_words"] = sorted(STOP)
    index["min_query_coverage"] = MIN_QUERY_COVERAGE
    index["collection"] = {key: manifest[key] for key in ("label", "scope", "currency_notice", "dataset", "revision", "license", "license_url")}
    index["sources"] = [{**{key: value for key, value in document.items() if key != "text"},
                         "word_count": len(document["text"].split())} for document in documents]
    retriever = Retriever(index)
    fixtures = [{"question": row["question"], "expected": answer(row["question"], retriever)}
                for row in read_jsonl(ROOT / "eval/consumer-law-dev.jsonl")]
    report = json.loads((ROOT / "reports/consumer-law-baseline.json").read_text())
    if report["corpus_sha256"] != index["corpus_sha256"]:
        raise ValueError("Evaluation report is for a different corpus; rerun the consumer-law evaluation")
    if report["questions_sha256"] != hashlib.sha256((ROOT / "eval/consumer-law-dev.jsonl").read_bytes()).hexdigest():
        raise ValueError("Evaluation questions changed; rerun evaluation before exporting")
    saved_answers = {row["question"]: row["answer"] for row in report["results"]}
    if any(saved_answers.get(row["question"]) != row["expected"]["answer"] for row in fixtures):
        raise ValueError("Retrieval behavior changed; rerun evaluation before exporting")
    evaluation = {"metrics": report["metrics"], "limitations": report["limitations"],
                  "corpus_sha256": report["corpus_sha256"], "questions_sha256": report["questions_sha256"],
                  "collection": index["collection"],
                  "results": [{key: row[key] for key in ("id", "question", "answerable", "retrieval_hit_at_1", "abstained")}
                              for row in report["results"]]}
    for filename, value in (("corpus.json", index), ("parity-fixtures.json", fixtures), ("evaluation.json", evaluation)):
        (output / filename).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"Exported {len(index['chunks'])} chunks and {len(fixtures)} parity fixtures")


if __name__ == "__main__":
    main()
