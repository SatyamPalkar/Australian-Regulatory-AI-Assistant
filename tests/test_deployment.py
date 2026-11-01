import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from reg_assistant.assistant import LocalController
from reg_assistant.deployment import RequestBudget, create_render_app
from reg_assistant.lexical import LexicalEvidenceRetriever, load_lexical_pipeline
from reg_assistant.core import ABSTENTION, read_jsonl
from reg_assistant.rag import ROOT


def model_controller():
    return LocalController(lambda _: json.dumps({"intent": "models", "relation": "new", "retailer": "none", "mention": "", "reason": ""}))


class DeploymentTests(unittest.TestCase):
    def app(self, **environment):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-not-a-real-key", **environment}, clear=True), \
             patch("reg_assistant.groq_backend.GroqController", side_effect=lambda _: model_controller()):
            return create_render_app()

    def test_missing_server_key_fails_startup_without_echoing_credentials(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "Configure GROQ_API_KEY"):
            create_render_app()

    def test_invalid_limits_and_origins_are_rejected(self):
        for env in [{"REGULATORY_REQUESTS_PER_DAY": "0"}, {"REGULATORY_REQUESTS_PER_DAY": "bad"},
                    {"REGULATORY_ALLOWED_ORIGINS": "http://unknown.test"},
                    {"REGULATORY_ALLOWED_ORIGINS": "https://example.test/path"},
                    {"REGULATORY_ALLOWED_ORIGINS": ""}]:
            with self.subTest(env=env), self.assertRaises(ValueError):
                self.app(**env)

    def test_health_status_and_truthful_lightweight_model_facts(self):
        with TestClient(self.app()) as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            status = client.get("/api/status").json()
            self.assertEqual(status["backend"], "tfidf")
            self.assertFalse(status["assistant"]["models"]["embedding"]["enabled"])
            self.assertFalse(status["assistant"]["models"]["reranker"]["enabled"])
            self.assertIn("disabled", status["retrieval_notice"])

    def test_unknown_browser_origin_and_non_json_are_blocked(self):
        with TestClient(self.app()) as client:
            self.assertEqual(client.post("/api/ask", json={"question": "models?"}, headers={"Origin": "https://untrusted.test"}).status_code, 403)
            self.assertEqual(client.post("/api/ask", content="a body").status_code, 415)

    def test_streamed_body_limit_applies_without_content_length(self):
        with TestClient(self.app()) as client:
            response = client.post("/api/ask", content=iter([b'x' * 9000, b'x' * 9000]), headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 413)

    def test_quota_rejection_has_cors_and_retry_after_without_model_calls(self):
        with TestClient(self.app(REGULATORY_REQUESTS_PER_DAY="1")) as client:
            headers = {"Origin": "https://satyampalkar.github.io"}
            self.assertEqual(client.post("/api/ask", json={"question": "models?"}, headers=headers).status_code, 200)
            response = client.post("/api/ask", json={"question": "models?"}, headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["access-control-allow-origin"], headers["Origin"])
            self.assertGreater(int(response.headers["retry-after"]), 0)

    def test_budget_caps_all_clients_and_resets_on_utc_boundaries(self):
        now = [120.0]
        budget = RequestBudget(per_minute=2, per_day=3, per_client=1, clock=lambda: now[0])
        self.assertTrue(budget.allow("a")[0])
        self.assertFalse(budget.allow("a")[0])
        self.assertTrue(budget.allow("b")[0])
        self.assertFalse(budget.allow("c")[0])
        now[0] += 60
        self.assertTrue(budget.allow("c")[0])
        self.assertFalse(budget.allow("d")[0])
        now[0] = 86400.0
        self.assertTrue(budget.allow("d")[0])

    def test_explicit_section_filter_and_unindexed_sections(self):
        retriever = LexicalEvidenceRetriever(read_jsonl(ROOT / "data/consumer_law.jsonl"))
        hits = retriever.search("What does section 54 require about acceptable quality?")
        self.assertTrue(hits)
        self.assertTrue(all(h["id"] == "acl-s54" for h in hits))
        self.assertEqual(retriever.search("What does section 999 say?"), [])

    def test_generation_retains_citation_checks_and_reports_no_reranker(self):
        class Generator:
            model_id = "test-hosted-model"
            def __call__(self, *_args, **_kwargs):
                return "Goods must be of acceptable quality. [1]"
        pipeline = load_lexical_pipeline(Generator())
        result = pipeline.ask("What does section 54 require about acceptable quality?")
        self.assertFalse(result["abstained"])
        self.assertIsNone(result["trace"]["reranker"])
        self.assertEqual(result["trace"]["retriever"], "tfidf")
        with patch.object(Generator, "__call__", return_value="Uncited assertion"):
            self.assertTrue(pipeline.ask("What does section 54 say about acceptable quality?")["abstained"])

    def test_unsupported_current_fee_does_not_call_generator(self):
        def forbidden(*_args, **_kwargs):
            self.fail("No generation should run without usable evidence")
        result = load_lexical_pipeline(forbidden).ask("What is the current NCAT application fee in Sydney?")
        self.assertEqual(result["answer"], ABSTENTION)

    def test_wording_only_followup_preserves_legal_topic_in_lexical_retrieval(self):
        first = "What does the supplier guarantee about the right to sell goods?"
        followup = "i still want to undersatnd it but in normal language sumarise it for mr"
        pipeline = load_lexical_pipeline(None)
        result = pipeline.ask(followup, search_question=first + "\nCurrent follow-up: " + followup)
        self.assertFalse(result["abstained"])
        self.assertEqual(result["mode"], "plain-language")
        self.assertEqual(result["evidence"][0]["id"], "acl-s51")
        self.assertEqual(result["trace"]["retrieval_query"], first)

    def test_lightweight_runtime_does_not_import_or_require_ml_packages(self):
        code = '''
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'torch','mlx','sentence_transformers','transformers'}:
   raise RuntimeError('Heavy ML dependency was imported')
sys.meta_path.insert(0, Block())
from reg_assistant.lexical import load_lexical_pipeline
p=load_lexical_pipeline(None)
assert p.ask('What does section 54 say about acceptable quality?')['evidence']
'''
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
