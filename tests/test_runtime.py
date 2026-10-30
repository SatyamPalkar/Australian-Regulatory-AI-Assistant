import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from reg_assistant.assistant import LocalController, conversation_result
from reg_assistant.runtime import runtime_snapshot, render_runtime_facts
from controller_fixtures import route


def manifest():
    return {role: {"repository": f"example/{role}-test", "revision": f"revision-{role}", "path": f"models/{role}"}
            for role in ["embedding", "reranker", "generator"]}


def corpus():
    return {"sources": [{"version_date": "2025-01-01"}, {"version_date": "2025-01-01"}],
            "chunks": [{}, {}, {}], "collection": {"label": "Test collection", "scope": "Selected test sections",
                                                       "currency_notice": "This is an older snapshot."}}


class RuntimeTests(unittest.TestCase):
    def test_snapshot_reads_names_counts_and_load_states_without_loading_models(self):
        facts = runtime_snapshot(corpus=corpus(), manifest=manifest())
        self.assertEqual(facts["models"]["controller"]["repository"], "example/generator-test")
        self.assertFalse(facts["models"]["controller"]["loaded"])
        self.assertFalse(facts["models"]["generator"]["loaded"])
        self.assertFalse(facts["answer_adapter"]["selected"])
        self.assertEqual(facts["corpus"]["section_count"], 2)
        self.assertEqual(facts["corpus"]["chunk_count"], 3)
        self.assertIsNone(facts["policy_tools"][0]["last_successful_fetch"])
        self.assertFalse(facts["policy_tools"][0]["indexed_in_statutory_corpus"])
        self.assertIn("not included", render_runtime_facts(facts, "DATA"))

    def test_answer_adapter_and_controller_are_independent_and_paths_are_not_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "test-adapter"
            adapter.mkdir()
            (adapter / "adapters.safetensors").touch()
            pipeline = SimpleNamespace(generator=SimpleNamespace(adapter=str(adapter), model=None),
                                       retriever=SimpleNamespace(encoder=object(), reranker=None))
            facts = runtime_snapshot(corpus=corpus(), manifest=manifest(), controller=SimpleNamespace(model=object()),
                                     pipeline=pipeline, adapter="ignored-config")
            self.assertTrue(facts["models"]["controller"]["loaded"])
            self.assertFalse(facts["models"]["controller"]["adapter"])
            self.assertTrue(facts["answer_adapter"]["selected"])
            self.assertTrue(facts["answer_adapter"]["weights_present"])
            self.assertFalse(facts["answer_adapter"]["loaded"])
            self.assertTrue(facts["models"]["embedding"]["loaded"])
            text = render_runtime_facts(facts, "MODELS")
            self.assertIn("test-adapter", text)
            self.assertNotIn(directory, text)
            self.assertIn("not loaded yet", text)
            pipeline.generator.model = object()
            self.assertTrue(runtime_snapshot(corpus=corpus(), manifest=manifest(), pipeline=pipeline)["answer_adapter"]["loaded"])

    def test_changed_configuration_changes_answer_without_a_rewritten_response(self):
        config = manifest()
        facts = lambda: runtime_snapshot(corpus=corpus(), manifest=config)
        outputs = iter([route("models"), route("models")])
        controller = LocalController(lambda _: next(outputs), runtime_facts=facts)
        first = controller.plan("Which models are configured?")
        config["generator"]["repository"] = "example/replacement-model"
        second = controller.plan("Tell me what powers the app")
        self.assertIn("example/generator-test", first["answer"])
        self.assertIn("example/replacement-model", second["answer"])
        self.assertNotIn("example/generator-test", second["answer"])
        result = conversation_result(second, 12, [])
        self.assertEqual(result["trace"]["response_strategy"], "runtime_facts")
        self.assertEqual(result["trace"]["generator"], "Runtime configuration renderer")
        self.assertEqual(result["runtime_facts"]["models"]["generator"]["repository"], "example/replacement-model")

    def test_model_selects_overview_without_generating_the_fact_values(self):
        outputs = iter([route("overview")])
        facts = runtime_snapshot(corpus=corpus(), manifest=manifest())
        result = LocalController(lambda _: next(outputs), runtime_facts=lambda: facts).plan("App capabilities?")
        self.assertEqual(result["fact_group"], "OVERVIEW")
        self.assertNotIn("InventedModel-999", result["answer"])
        self.assertIn("example/embedding-test", result["answer"])
        self.assertIn("No successful policy fetch", result["answer"])

    def test_api_answers_with_same_facts_as_status_without_search_or_policy_fetch(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        outputs = iter([route("models")])
        controller = LocalController(lambda _: next(outputs))
        with patch("reg_assistant.api.model_manifest", side_effect=manifest), \
             patch("reg_assistant.api.load_pipeline") as load, patch("reg_assistant.api.answer_policy") as fetch:
            with TestClient(create_app(controller=controller)) as client:
                response = client.post("/api/ask", json={"question": "which model are being used"})
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(result["runtime_facts"], client.get("/api/status").json()["assistant"])
                self.assertFalse(result["abstained"])
                self.assertEqual(result["mode"], "conversation")
                self.assertIn("example/reranker-test", result["answer"])
            load.assert_not_called()
            fetch.assert_not_called()

    def test_policy_success_is_retained_after_failure_but_not_across_servers(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        from test_retailer import fixture
        class PolicyController:
            def plan(self, question, history, state=None):
                return {"action": "policy", "provider": "jb_hifi", "answer": ""}
        with TestClient(create_app(controller=PolicyController(), policy_fetcher=fixture)) as client:
            initial = client.get("/api/status").json()["assistant"]["policy_tools"][0]
            self.assertEqual(initial["last_attempt_status"], "not_requested")
            response = client.post("/api/ask", json={"question": "JB Hi-Fi returns?"}).json()
            fetched = response["evidence"][0]["fetched_at"]
            after_success = client.get("/api/status").json()["assistant"]["policy_tools"][0]
            self.assertEqual(after_success["last_successful_fetch"], fetched)
            with patch("reg_assistant.retailer.policy_passages", side_effect=ValueError("changed schema")):
                client.post("/api/ask", json={"question": "JB Hi-Fi returns?"})
            after_failure = client.get("/api/status").json()["assistant"]["policy_tools"][0]
            self.assertEqual(after_failure["last_attempt_status"], "unavailable")
            self.assertEqual(after_failure["last_successful_fetch"], fetched)
            text = render_runtime_facts(client.get("/api/status").json()["assistant"], "TOOLS")
            self.assertIn("unavailable", text)
            self.assertIn(fetched, text)
        with TestClient(create_app(controller=PolicyController())) as client:
            self.assertIsNone(client.get("/api/status").json()["assistant"]["policy_tools"][0]["last_successful_fetch"])
