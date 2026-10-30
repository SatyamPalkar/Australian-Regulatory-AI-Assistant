"""Download a controller's pinned public revision without changing the RAG model."""
import argparse
import json
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=ROOT/"configs/controller.json")
    args=parser.parse_args()
    spec=json.loads(args.manifest.read_text())
    snapshot_download(spec["repository"],revision=spec["revision"],token=False,
                      local_dir=ROOT/spec["path"],cache_dir=ROOT/".cache/huggingface",
                      allow_patterns=["*.json","*.jinja","*.safetensors","*.txt","*.model","README.md","LICENSE"])
    print("Pinned controller ready; the RAG generator and adapters are unchanged.")


if __name__=="__main__":main()
