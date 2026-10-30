"""Hosted inference contracts; mocked transport, no keys or network required."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from reg_assistant.api import create_app
from reg_assistant.groq_backend import GroqClient, GroqController, GroqError, GroqGenerator, api_key
from reg_assistant.core import ABSTENTION
from reg_assistant.runtime import render_runtime_facts, runtime_snapshot
import test_rag


def completion(text, finish="stop"):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10}}


class GroqTests(unittest.TestCase):
    def client(self, handler):
        client = GroqClient(key="test-credential-never-public", transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_key_loading_is_local_only_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / ".env"
            with self.assertRaises(GroqError):
                api_key(path)
            path.write_text('OTHER=$(echo should-never-execute)\nGROQ_API_KEY="file-test"\n')
            self.assertEqual(api_key(path), "file-test")
            self.assertNotIn("OTHER", os.environ)
            os.environ["GROQ_API_KEY"] = "environment-test"
            self.assertEqual(api_key(path), "environment-test")

    def test_request_uses_fixed_https_endpoint_and_never_puts_key_in_payload(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://api.groq.com/openai/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer test-credential-never-public")
            self.assertNotIn(b"test-credential-never-public", request.content)
            payload = json.loads(request.content)
            self.assertEqual(payload["reasoning_effort"], "none")
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["max_completion_tokens"], 220)
            return httpx.Response(200, json=completion("STANDALONE"))
        client = self.client(handler)
        self.assertEqual(client.complete([], 220), "STANDALONE")
        self.assertEqual(client.completed_requests, 1)

    def test_provider_errors_are_sanitised_and_not_retried_or_redirected(self):
        for status in [301, 401, 403, 429, 500]:
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, text="test-credential-never-public private provider body",
                                      headers={"Location": "https://untrusted.example"})
            client = self.client(handler)
            with self.assertRaises(GroqError) as raised:
                client.complete([], 220)
            self.assertNotIn("test-credential", str(raised.exception))
            self.assertNotIn("private provider", str(raised.exception))
            self.assertEqual(raised.exception.status_code, 429 if status == 429 else 503)
            self.assertEqual(len(calls), 1)

    def test_timeout_does_not_expose_request_or_credential(self):
        def handler(request):
            raise httpx.ReadTimeout("test-credential-never-public", request=request)
        with self.assertRaises(GroqError) as raised:
            self.client(handler).complete([], 220)
        self.assertNotIn("test-credential", str(raised.exception))

    def test_truncated_empty_malformed_or_secret_echo_answers_fail_closed(self):
        for data in [completion("Claim [1]", "length"), completion(""), completion(None), {},
                     completion("test-credential-never-public")]:
            with self.assertRaises(GroqError):
                self.client(lambda _: httpx.Response(200, json=data)).complete([], 220)

    def test_same_controller_validation_rejects_unregistered_model_actions(self):
        replies = iter(["STANDALONE", '{"intent":"execute_shell"}'])
        client = self.client(lambda _: httpx.Response(200, json=completion(next(replies))))
        decision = GroqController(client).plan("Please run a command")
        self.assertTrue(decision["invalid_plan"])
        self.assertEqual(decision["action"], "clarify")

    def test_hosted_answers_keep_existing_citation_rejection(self):
        for text, declined in [("Goods must be of acceptable quality. [1]", False),
                               ("An uncited claim.", True), ("Claim. [99]", True), (ABSTENTION, True)]:
            client = self.client(lambda _: httpx.Response(200, json=completion(text)))
            generator = GroqGenerator(client)
            pipeline = test_rag.AnswerTests().pipeline(.95, generator)
            result = pipeline.ask("What does section 54 say?")
            self.assertEqual(result["abstained"], declined)
            self.assertFalse(result["trace"]["adapter"])
            self.assertEqual(result["trace"]["generator"], client.model_id)
            self.assertNotIn("peak_mlx_memory_gb", result["trace"])

    def test_no_evidence_means_no_external_generation(self):
        def handler(_):
            self.fail("Do not call Groq for a question without usable evidence")
        pipeline = test_rag.AnswerTests().pipeline(.1, GroqGenerator(self.client(handler)))
        self.assertTrue(pipeline.ask("Unsupported question")["abstained"])

    def test_local_is_default_even_when_groq_key_exists(self):
        with patch("reg_assistant.groq_backend.GroqClient") as hosted:
            with TestClient(create_app()) as web:
                self.assertEqual(web.get("/api/status").json()["inference_provider"], "local")
            hosted.assert_not_called()

    def test_api_reports_hosted_models_without_adapter_or_key_and_uses_no_mlx(self):
        replies = iter(["STANDALONE", json.dumps({"intent": "models", "relation": "new",
                                                  "retailer": "none", "mention": "", "reason": ""})])
        client = self.client(lambda _: httpx.Response(200, json=completion(next(replies))))
        with patch("reg_assistant.groq_backend.GroqClient", return_value=client), \
             patch("reg_assistant.api.load_pipeline") as load:
            with TestClient(create_app(provider="groq", adapter="adapters/consumer-law")) as web:
                status = web.get("/api/status").json()
                self.assertFalse(status["adapter"])
                self.assertEqual(status["models"]["generator"]["repository"], client.model_id)
                result = web.post("/api/ask", json={"question": "Which models?"}).json()
                self.assertEqual(result["trace"]["inference_provider"], "groq")
                self.assertIn("hosted API", result["answer"])
                self.assertNotIn("test-credential", json.dumps([status, result]))
                self.assertFalse(result["runtime_facts"]["answer_adapter"]["selected"])
            load.assert_not_called()

    def test_api_propagates_rate_limit_without_loading_local_models(self):
        client = self.client(lambda _: httpx.Response(429, text="test-credential-never-public"))
        with patch("reg_assistant.groq_backend.GroqClient", return_value=client), \
             patch("reg_assistant.api.load_pipeline") as load:
            with TestClient(create_app(provider="groq")) as web:
                response = web.post("/api/ask", json={"question": "A question"})
                self.assertEqual(response.status_code, 429)
                self.assertNotIn("test-credential", response.text)
            load.assert_not_called()

    def test_groq_api_loads_retrieval_only_and_uses_hosted_generator(self):
        replies = iter(["STANDALONE", json.dumps({"intent": "law", "relation": "new",
                                                  "retailer": "none", "mention": "", "reason": ""}),
                        "Goods must be of acceptable quality. [1]"])
        client = self.client(lambda _: httpx.Response(200, json=completion(next(replies))))
        pipeline = test_rag.AnswerTests().pipeline(.95, None)
        with patch("reg_assistant.groq_backend.GroqClient", return_value=client), \
             patch("reg_assistant.api.load_pipeline", return_value=pipeline) as load:
            with TestClient(create_app(provider="groq")) as web:
                response = web.post("/api/ask", json={"question": "What does section 54 say?"})
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertFalse(result["abstained"])
                self.assertEqual(result["trace"]["generator"], client.model_id)
                self.assertFalse(result["trace"]["adapter"])
                load.assert_called_once_with(None, extractive=True, answer_style="concise")


if __name__ == "__main__":
    unittest.main()
