import hashlib
import json
import unittest
from pathlib import Path

from reg_assistant.core import ABSTENTION, build_index, read_jsonl
from reg_assistant.rag import (HybridRetriever, RAGPipeline, model_manifest,
                               validate_citations)

ROOT = Path(__file__).resolve().parents[1]


class Encoder:
    def encode(self, *_args, **_kwargs):
        return [[1.0, 0.0]]


class Reranker:
    def __init__(self, scores):
        self.scores = scores

    def predict(self, pairs, **_kwargs):
        self.pairs = pairs
        return self.scores[:len(pairs)]


class HybridTests(unittest.TestCase):
    def index(self):
        docs = read_jsonl(ROOT / "data/consumer_law.jsonl")
        index = build_index([d for d in docs if d["section_number"] in ["18", "60"]])
        return {**index, "backend": "hybrid", "model_manifest": model_manifest(),
                "dense_vectors": [[0.0, 1.0], [1.0, 0.0]]}

    def test_reranker_orders_fused_candidates_and_preserves_provenance(self):
        reranker = Reranker([-4, 7])
        retriever = HybridRetriever(self.index(), Encoder(), reranker)
        result = retriever.search("services supplied with skill", 2)
        self.assertGreater(result[0]["score"], result[1]["score"])
        self.assertEqual(result[0]["dataset"], "cchew/lex-au")
        self.assertEqual(len(reranker.pairs), 2)

    def test_invalid_model_scores_fail_closed(self):
        for score in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(score=score), self.assertRaisesRegex(RuntimeError, "non-finite"):
                HybridRetriever(self.index(), Encoder(), Reranker([score, 1])).search("services")

    def test_explicit_section_filters_candidates(self):
        reranker = Reranker([5, 5])
        hits = HybridRetriever(self.index(), Encoder(), reranker).search("What does section 18 prohibit?")
        self.assertTrue(all(h["id"] == "acl-s18" for h in hits))
        self.assertEqual(len(reranker.pairs), 1)

    def test_changed_model_revision_requires_reindex(self):
        index = self.index()
        index["model_manifest"] = {}
        with self.assertRaisesRegex(ValueError, "revisions"):
            HybridRetriever(index, Encoder(), Reranker([1]))


class AnswerTests(unittest.TestCase):
    def test_every_paragraph_requires_existing_reference(self):
        self.assertTrue(validate_citations("A supported statement. [1]\n\nAnother. [2]", 2))
        self.assertTrue(validate_citations(ABSTENTION, 0))
        for text in ["Claim without a source.", "Claim [99]", "Claim [0]", "Uncited claim.\n\nCited claim. [1]"]:
            self.assertFalse(validate_citations(text, 2))

    def pipeline(self, score, generator):
        index = build_index([d for d in read_jsonl(ROOT / "data/consumer_law.jsonl") if d["id"] == "acl-s54"])
        class Retrieved:
            def __init__(self):
                self.index = {**index, "backend": "hybrid"}
            def search(self, *_args):
                return [{**c, "score": score} for c in self.index["chunks"][:3]]
        return RAGPipeline(Retrieved(), generator)

    def test_no_evidence_skips_generation(self):
        def fail(*_args):
            self.fail("No generation should happen without evidence")
        result = self.pipeline(.01, fail).ask("Is this supported?")
        self.assertTrue(result["abstained"])

    def test_full_short_section_includes_later_exceptions_and_deduplicates(self):
        seen = []
        def generate(_q, evidence):
            seen.extend(evidence)
            return "Goods must be durable. [1]"
        result = self.pipeline(.9, generate).ask("Does quality include durability?")
        original = next(d for d in read_jsonl(ROOT / "data/consumer_law.jsonl") if d["id"] == "acl-s54")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["text"], original["text"])
        self.assertEqual(seen[0]["evidence_span"], "full_section")
        self.assertFalse(result["abstained"])

    def test_rejected_output_is_separate_from_user_answer(self):
        result = self.pipeline(.9, lambda *_: "Invented claim without references").ask("quality?")
        self.assertEqual(result["answer"], ABSTENTION)
        self.assertFalse(result["citation_format_valid"])
        self.assertEqual(result["raw_generation"], "Invented claim without references")


class FrozenSplitTests(unittest.TestCase):
    def test_split_hashes_and_source_disjointness(self):
        manifest = json.loads((ROOT / "eval/split-manifest.json").read_text())
        for name, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)
        train = {s for split in ["train", "valid"] for row in read_jsonl(ROOT / f"data/training/{split}.jsonl") for s in row["source_ids"]}
        test = {s for row in read_jsonl(ROOT / "eval/benchmark-v1.jsonl") for s in row["expected_sources"]}
        self.assertFalse(train & test)
        self.assertEqual(len(read_jsonl(ROOT / "eval/benchmark-v1.jsonl")), 36)


if __name__ == "__main__":
    unittest.main()
