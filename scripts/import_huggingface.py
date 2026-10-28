"""Run from the repo root; network is needed only for uncached pinned files."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.huggingface import import_huggingface


def main():
    parser = argparse.ArgumentParser(description="Import actual Australian Consumer Law from Hugging Face")
    parser.add_argument("--manifest", default="data/huggingface_sources.json")
    parser.add_argument("--output", default="data/consumer_law.jsonl")
    parser.add_argument("--cache", default="data/raw/huggingface")
    args = parser.parse_args()
    try:
        count = import_huggingface(args.manifest, args.output, args.cache)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"Imported {count} statutory sections into {args.output}")


if __name__ == "__main__":
    main()
