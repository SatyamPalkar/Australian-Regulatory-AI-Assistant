"""Export the Python baseline and fixtures for the deployed retrieval engine."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import STOP, Retriever, answer, build_index, read_jsonl


def main():
    output = ROOT / "site/lib"
    output.mkdir(parents=True, exist_ok=True)
    index = build_index(read_jsonl(ROOT / "data/demo.jsonl"))
    index.pop("created_at")
    index["stop_words"] = sorted(STOP)
    (output / "corpus.json").write_text(json.dumps(index, indent=2) + "\n")
    retriever = Retriever(index)
    fixtures = [{"question": row["question"], "expected": answer(row["question"], retriever)}
                for row in read_jsonl(ROOT / "eval/dev.jsonl")]
    (output / "parity-fixtures.json").write_text(json.dumps(fixtures, indent=2) + "\n")
    report = json.loads((ROOT / "reports/dev-baseline.json").read_text())
    evaluation = {"metrics": report["metrics"], "limitations": report["limitations"],
                  "corpus_sha256": report["corpus_sha256"], "questions_sha256": report["questions_sha256"],
                  "results": [{key: row[key] for key in ("id", "question", "answerable", "retrieval_hit_at_1", "abstained")}
                              for row in report["results"]]}
    (output / "evaluation.json").write_text(json.dumps(evaluation, indent=2) + "\n")
    print(f"Exported {len(index['chunks'])} chunks and {len(fixtures)} parity fixtures")


if __name__ == "__main__":
    main()
