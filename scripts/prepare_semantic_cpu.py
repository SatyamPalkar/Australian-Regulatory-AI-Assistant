"""Build-time download of pinned public assets and corpus embeddings, never at query time."""
import argparse
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reg_assistant.core import read_jsonl
from reg_assistant.semantic_cpu import ROOT, CPUEncoder, build_semantic_index, configuration, verify_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use already downloaded, hash-verified assets")
    args = parser.parse_args()
    spec = configuration()
    directory = ROOT / spec["path"]
    directory.mkdir(parents=True, exist_ok=True)
    for name, metadata in spec["files"].items():
        target = directory / name
        try:
            verify_file(target, metadata["sha256"])
            continue
        except RuntimeError:
            if args.offline:
                raise
        url = f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{metadata['source']}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            verify_file(temporary, metadata["sha256"])
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Could not prepare pinned embedding asset; check build network access") from None
    result = build_semantic_index(read_jsonl(ROOT / "data/consumer_law.jsonl"), CPUEncoder())
    print(f"Prepared {len(result['vectors'])} CPU semantic vectors; no reranker or local LLM loaded.")


if __name__ == "__main__":
    main()
