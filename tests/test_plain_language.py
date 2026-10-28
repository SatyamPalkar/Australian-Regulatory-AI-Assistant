import hashlib
import unittest

from reg_assistant.core import ABSTENTION, read_jsonl
from reg_assistant.plain_language import guides, plain_language_summary
from reg_assistant.rag import ROOT, RAGPipeline, validate_citations


class PlainLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {d["id"]: d for d in read_jsonl(ROOT / "data/consumer_law.jsonl")}

    def test_every_guide_matches_current_source_hash_and_supporting_anchors(self):
        for source_id, guide in guides().items():
            source = self.documents[source_id]
            self.assertEqual(hashlib.sha256(source["text"].encode()).hexdigest(), guide["source_text_sha256"])
            self.assertTrue(all(anchor in source["text"] for anchor in guide["source_anchors"]))
            self.assertTrue(validate_citations(plain_language_summary(source), 1))

    def test_changed_source_or_missing_guide_never_reuses_a_prepared_summary(self):
        source = self.documents["acl-s51"]
        self.assertIsNone(plain_language_summary({**source, "text": source["text"] + " Changed."}))
        self.assertIsNone(plain_language_summary({**source, "version_date": "2027-01-01"}))
        self.assertIsNone(plain_language_summary({**source, "compilation_id": "changed"}))
        self.assertIsNone(plain_language_summary(self.documents["acl-s62"]))

    def pipeline(self, source_id="acl-s51", score=.99):
        source = self.documents[source_id]
        class Retrieved:
            index = {"backend": "hybrid"}
            def search(self, question, k):
                return [{**source, "chunk_id": f"{source_id}:test", "score": score, "rerank_logit": 6}]
        def fail(*_args, **_kwargs):
            self.fail("Prepared summaries must not call the generative model")
        return RAGPipeline(Retrieved(), fail)

    def test_prepared_summary_is_plain_cited_and_clearly_distinct_from_model_output(self):
        history = [{"question": "What does the supplier guarantee about the right to sell goods?", "answer": "Invented prior claim [999]."}]
        result = self.pipeline().ask("i still want to undersatnd it but in normal language sumarise it for mr", history)
        self.assertEqual(result["mode"], "plain-language")
        self.assertIn("legal right to sell", result["answer"])
        self.assertIn("hiring or leasing", result["answer"])
        self.assertNotIn("[999]", result["answer"])
        self.assertEqual(result["trace"]["response_strategy"], "prepared_summary")
        self.assertIsNone(result["trace"]["generator"])
        self.assertFalse(result["trace"]["adapter"])
        self.assertTrue(result["citation_format_valid"])
        self.assertEqual(len(result["evidence"]), 1)

    def test_summary_request_still_needs_fresh_qualifying_evidence(self):
        result = self.pipeline(score=.01).ask("summarise it", [{"question": "Explain title", "answer": "Old claim"}])
        self.assertEqual(result["answer"], ABSTENTION)

    def test_uncovered_source_returns_labelled_source_text(self):
        result = self.pipeline("acl-s62").ask("summarise it", [{"question": "Explain section 62", "answer": "Old answer"}])
        self.assertEqual(result["mode"], "source-quotes")
        self.assertIn("not available", result["scope_note"])


if __name__ == "__main__":
    unittest.main()
