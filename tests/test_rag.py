import hashlib
import json
import unittest
from pathlib import Path

from reg_assistant.core import ABSTENTION, build_index, read_jsonl
from reg_assistant.rag import (HybridRetriever, RAGPipeline, model_manifest,
                               statutory_search_query, validate_citations)

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

    def test_everyday_warranty_words_reach_the_reranker_as_statutory_terms(self):
        reranker = Reranker([5, 4])
        retriever = HybridRetriever(self.index(), Encoder(), reranker)
        retriever.search("what are the warranties on electronics products")
        self.assertTrue(all(q == "what are the express warranties on goods" for q, _ in reranker.pairs))

    def test_query_rewrite_preserves_brand_duration_and_missing_information(self):
        query = statutory_search_query("What is Samsung's 24 month warranty on electronics products in NSW?")
        for detail in ["Samsung", "24 month", "NSW"]:
            self.assertIn(detail, query)
        self.assertIn("current NCAT fee", statutory_search_query("What is the current NCAT fee for an electronics warranty complaint?"))
        self.assertEqual(statutory_search_query("What does section 18 say?"), "What does section 18 say?")
        original = "Does a supplier have to comply with an express warranty?"
        self.assertEqual(statutory_search_query(original), original)

    def test_frozen_benchmark_questions_keep_identical_search_wording(self):
        for row in read_jsonl(ROOT / "eval/benchmark-v1.jsonl"):
            self.assertEqual(statutory_search_query(row["question"]), row["question"], row["id"])


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

    def test_generator_receives_original_question_not_the_search_rewrite(self):
        original = "what are the warranties on electronics products"
        def generate(question, _evidence):
            self.assertEqual(question, original)
            return "Goods must be durable. [1]"
        result = self.pipeline(.9, generate).ask(original)
        self.assertEqual(result["trace"]["retrieval_query"], "what are the express warranties on goods")

    def test_rewritten_warranty_query_does_not_mix_in_weakly_related_provisions(self):
        documents = read_jsonl(ROOT / "data/consumer_law.jsonl")
        index = build_index([d for d in documents if d["id"] in ["acl-s59", "acl-s57"]])
        hits = [{**next(c for c in index["chunks"] if c["id"] == source), "score": score, "rerank_logit": logit}
                for source, score, logit in [("acl-s59", .998, 6), ("acl-s57", .73, 1)]]
        class Retrieved:
            def __init__(self):
                self.index = {**index, "backend": "hybrid"}
            def search(self, *_args):
                return hits
        def generate(_question, evidence):
            self.assertEqual([e["id"] for e in evidence], ["acl-s59"])
            return "The manufacturer must comply with its express warranty. [1]"
        result = RAGPipeline(Retrieved(), generate).ask("What warranties apply to a laptop?")
        self.assertFalse(result["abstained"])
        self.assertIn("Brand-specific", result["scope_note"])

    def test_rewritten_question_still_requires_the_original_evidence_threshold(self):
        def fail(*_args):
            self.fail("A rewrite must not force generation on weak evidence")
        result = self.pipeline(.01, fail).ask("What warranties apply to electronics products?")
        self.assertTrue(result["abstained"])
        self.assertIsNone(result["scope_note"])


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
