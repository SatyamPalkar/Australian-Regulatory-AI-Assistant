"""Project-authored plain-language guides pinned to exact statutory source text."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def guides():
    return json.loads((ROOT / "data/plain_language_guides.json").read_text())["guides"]


def plain_language_summary(document):
    guide = guides().get(document["id"])
    if not guide:
        return None
    digest = hashlib.sha256(document["text"].encode()).hexdigest()
    if (digest != guide["source_text_sha256"] or document.get("version_date") != guide["source_version"]
            or document.get("compilation_id") != guide["compilation_id"] or document.get("law_id") != guide["law_id"]):
        return None
    if not all(anchor in document["text"] for anchor in guide["source_anchors"]):
        return None
    return "\n\n".join(f"{paragraph} [1]" for paragraph in guide["paragraphs"])
