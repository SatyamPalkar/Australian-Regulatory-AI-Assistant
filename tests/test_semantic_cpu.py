import copy
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from reg_assistant.core import build_index, read_jsonl
from reg_assistant.rag import ROOT, RAGPipeline
from reg_assistant.semantic_cpu import (SemanticCPURetriever, configuration, config_digest,
                                        validate_index, verify_file)
import test_deployment


class SemanticCPUTests(unittest.TestCase):
    def fixture(self):
        docs = read_jsonl(ROOT / "data/consumer_law.jsonl")[:2]
        lexical = build_index(docs)
        vectors = [[1.0] + [0.0] * 383 for _ in lexical["chunks"]]
        dense = {"version": 1, "config_sha256": config_digest(configuration()),
                 "corpus_sha256": lexical["corpus_sha256"],
                 "chunk_ids": [c["chunk_id"] for c in lexical["chunks"]], "vectors": vectors}
        class Encoder:
            def encode(self, texts):
                return [[1.0] + [0.0] * 383 for _ in texts]
        return docs, lexical, dense, Encoder()

    def test_default_render_profile_reports_embeddings_enabled_without_loading_models(self):
        helper = test_deployment.DeploymentTests()
        with TestClient(helper.app()) as client:
            status = client.get("/api/status").json()
            self.assertEqual(status["backend"], "semantic_cpu")
            spec = status["assistant"]["models"]["embedding"]
            self.assertTrue(spec["enabled"])
            self.assertFalse(spec["loaded"])
            self.assertIn("ONNX", spec["runtime"])
            self.assertFalse(status["assistant"]["models"]["reranker"]["enabled"])
            self.assertFalse(status["adapter"])

    def test_semantic_search_can_admit_evidence_without_lexical_overlap(self):
        docs, _, dense, encoder = self.fixture()
        retriever = SemanticCPURetriever(docs, encoder=encoder, dense=dense)
        hits = retriever.search("xyzzy quux")
        self.assertTrue(hits[0]["eligible"])
        self.assertEqual(hits[0]["lexical_score"], 0)
        self.assertEqual(hits[0]["score"], 1)
        self.assertEqual(len({h["id"] for h in hits}), len(hits))

    def test_low_semantic_similarity_rejects_even_lexical_matches_and_skips_generation(self):
        docs, _, dense, encoder = self.fixture()
        encoder.encode = lambda texts: [[0.0, 1.0] + [0.0] * 382 for _ in texts]
        retriever = SemanticCPURetriever(docs, encoder=encoder, dense=dense)
        def forbidden(*args):
            self.fail("Unqualified evidence must not reach generation")
        result = RAGPipeline(retriever, forbidden, min_score=-1).ask(docs[0]["title"])
        self.assertTrue(result["abstained"])
        self.assertFalse(result["evidence"])

    def test_corrupt_stale_or_mismatched_index_fails_closed(self):
        _, lexical, dense, _ = self.fixture()
        for key, value in [("version", 2), ("corpus_sha256", "stale"),
                           ("config_sha256", "stale"), ("chunk_ids", []), ("vectors", [])]:
            bad = {**dense, key: value}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                validate_index(bad, lexical)
        for vector in [[float("nan")] * 384, [0.0] * 384, [1.0] * 383]:
            bad = copy.deepcopy(dense)
            bad["vectors"][0] = vector
            with self.assertRaises(RuntimeError):
                validate_index(bad, lexical)

    def test_asset_hash_mismatch_or_missing_asset_fails_before_model_import(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset"
            with self.assertRaises(RuntimeError):
                verify_file(path, "0" * 64)
            path.write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                verify_file(path, "0" * 64)

    def test_explicit_unindexed_section_does_not_return_other_sections(self):
        docs, _, dense, encoder = self.fixture()
        retriever = SemanticCPURetriever(docs, encoder=encoder, dense=dense)
        self.assertEqual(retriever.search("Explain section 999"), [])

    def test_invalid_query_embedding_is_rejected(self):
        docs, _, dense, encoder = self.fixture()
        encoder.encode = lambda texts: [[float("nan")] * 384]
        with self.assertRaises(RuntimeError):
            SemanticCPURetriever(docs, encoder=encoder, dense=dense).search("a question")


if __name__ == "__main__":
    unittest.main()
