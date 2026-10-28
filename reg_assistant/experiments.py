"""Dependency-free integrity checks for the second experiment."""
import hashlib
import json

from .core import read_jsonl
from .rag import ROOT


def verify_phase2():
    manifest = json.loads((ROOT / "eval/phase2-manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen phase 2 file changed: {name}")
    digest = hashlib.sha256(json.dumps(read_jsonl(ROOT / "data/consumer_law.jsonl"), sort_keys=True).encode()).hexdigest()
    if digest != manifest["corpus_sha256"]:
        raise ValueError("Phase 2 corpus changed")
    return manifest
