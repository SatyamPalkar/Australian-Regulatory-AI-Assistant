import unittest
from unittest.mock import patch

from reg_assistant.retailer import answer_policy, policy_passages, retailer_intent, NoRedirect


def paragraph(text):
    return {"nodeType": "paragraph", "content": [{"nodeType": "text", "value": text}]}


def fixture():
    # Synthetic text: not a copy of the retailer's live policy.
    return {"data": {"items": [{"fields": {
        "legacyId": "360053005194", "heading": "Refunds & Warranties guide",
        "mainBody": {"content": [
            paragraph("This Guide applies to direct purchases. Marketplace sellers have their own policies."),
            paragraph("Our goods come with guarantees. Faults need assessment."),
            {"nodeType": "heading-2", "content": [{"nodeType": "text", "value": "Media products"}]},
            {"nodeType": "table", "content": [
                {"nodeType": "table-row", "content": [paragraph("Status"), paragraph("Limit"), paragraph("Exclusions")]},
                {"nodeType": "table-row", "content": [paragraph("Unused & Unopened"), paragraph("Test period"), paragraph("Software excluded")]},
            ]},
            paragraph("Keep proof of purchase for assessment."),
        ]}}}]}}


class RetailerTests(unittest.TestCase):
    def test_variants_and_statutory_queries(self):
        for question in ["what are the jb hifi return policy", "JB Hi-Fi refunds?", "jbhifi warranty"]:
            self.assertTrue(retailer_intent(question))
        for question in ["What is section 54?", "What is the NCAT fee?", "JB Hi-Fi share price?", "https://evil.test/refunds"]:
            self.assertFalse(retailer_intent(question))

    def test_dependent_followup_and_topic_change(self):
        history = [{"question": "JB Hi-Fi return policy?", "answer": "untrusted history"}]
        self.assertTrue(retailer_intent("I opened it, can I return it?", history))
        for q in ["What does section 51 say?", "Can I return this to Kmart?", "Can I apply to NCAT?"]:
            self.assertFalse(retailer_intent(q, history))

    def test_tables_keep_category_headers_and_exclusions(self):
        passages = policy_passages(fixture())
        self.assertIn("Media products\nStatus | Limit | Exclusions\nUnused & Unopened | Test period | Software excluded", passages)
        result = answer_policy("JB Hi-Fi returns?", fetcher=fixture)
        self.assertEqual(result["policy_lookup"]["status"], "fetched")
        self.assertEqual(len(result["evidence"]), 4)
        self.assertIn("Marketplace", result["answer"])
        self.assertIn("fetched_at", result["evidence"][0])
        self.assertEqual(result["evidence"][0]["source_kind"], "retailer_policy")

    def test_failure_and_changed_schema_have_no_false_citations_or_terms(self):
        for fetcher in [lambda: {}, lambda: (_ for _ in ()).throw(OSError("offline"))]:
            result = answer_policy("JB Hi-Fi return policy?", fetcher=fetcher)
            self.assertFalse(result["abstained"])
            self.assertEqual(result["policy_lookup"]["status"], "unavailable")
            self.assertEqual(result["evidence"], [])
            self.assertNotIn("[1]", result["answer"])
            self.assertIn("faulty", result["answer"])

    def test_unrelated_question_never_fetches_and_redirects_are_rejected(self):
        with patch("reg_assistant.retailer.fetch_policy") as fetch:
            self.assertIsNone(answer_policy("What is section 51?"))
            fetch.assert_not_called()
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.test")

    def test_api_policy_does_not_load_the_model(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        class Controller:
            def plan(self, question, history, state=None):
                return {"action": "policy", "provider": "jb_hifi", "answer": ""}
        with patch("reg_assistant.api.load_pipeline") as load:
            with TestClient(create_app(policy_fetcher=fixture, controller=Controller())) as client:
                response = client.post("/api/ask", json={"question": "JB Hi-Fi refund policy?"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["policy_lookup"]["status"], "fetched")
                self.assertFalse(client.get("/api/health").json()["models_loaded"])
            load.assert_not_called()
