"""Resolve model revisions once, then reproduce downloads from the saved manifest."""
import argparse
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "embedding": "sentence-transformers/all-MiniLM-L6-v2",
    "reranker": "cross-encoder/ms-marco-MiniLM-L6-v2",
    "generator": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true", help="Explicitly resolve and save new immutable revisions")
    args = parser.parse_args()
    path = ROOT / "configs/models.json"
    if args.resolve:
        api = HfApi()
        manifest = {role: {"repository": name, "revision": api.model_info(name).sha,
                           "path": f"models/{role}", "license": "apache-2.0"}
                    for role, name in MODELS.items()}
        path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest = json.loads(path.read_text())
    for role, item in manifest.items():
        print(f"Downloading {role}: {item['repository']} @ {item['revision']}", flush=True)
        snapshot_download(item["repository"], revision=item["revision"],
                          local_dir=ROOT / item["path"],
                          allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "README.md"])
    print("Models ready. Model weights remain ignored by Git.")


if __name__ == "__main__":
    main()
