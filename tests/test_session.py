import unittest
from unittest.mock import patch

from reg_assistant.assistant import LocalController
from reg_assistant.session import ConversationState, SessionStore
from controller_fixtures import route


class SessionTests(unittest.TestCase):
    def test_store_isolated_bounded_and_expires(self):
        clock = [0]
        store = SessionStore(limit=2, ttl_seconds=10, clock=lambda: clock[0])
        first, state = store.get(); state.retailer = "jb_hifi"
        clock[0] = 1
        second, other = store.get()
        self.assertEqual(other.retailer, "none")
        clock[0] = 2
        third, _ = store.get()
        with self.assertRaises(KeyError): store.get(first)
        self.assertEqual(store.get(second)[0], second)
        clock[0] = 20
        with self.assertRaises(KeyError): store.get(third)
        self.assertLessEqual(len(store._sessions), 2)

    def test_one_clarification_then_recovery_until_a_real_task(self):
        state = ConversationState()
        controller = LocalController(lambda _: route("clarify", reason="ambiguous"))
        for turn in range(5):
            decision = controller.plan("unclear", state=state)
            self.assertEqual(decision["action"], "clarify" if turn == 0 else "recovery")
            state.advance("unclear", decision)
        self.assertEqual(state.clarification_attempts, 5)
        self.assertTrue(decision["quick_actions"])
        controller.generate = lambda _: route("models")
        decision = controller.plan("Show the models", state=state); state.advance("Show the models", decision)
        self.assertEqual(state.clarification_attempts, 0)
        self.assertEqual(state.pending_clarification, "")

    def test_explicit_new_topic_discards_old_retailer_and_search_anchor(self):
        state = ConversationState(topic_question="JB Hi-Fi returns", active_intent="policy", retailer="jb_hifi")
        decision = LocalController(lambda _: route("law")).plan("Consequences of rejecting goods", state=state)
        self.assertEqual(decision["search_question"], "Consequences of rejecting goods")
        state.advance("Consequences of rejecting goods", decision)
        self.assertEqual(state.retailer, "none")
        self.assertEqual(state.topic_question, "Consequences of rejecting goods")

    def test_other_retailer_cannot_inherit_jb_policy(self):
        state = ConversationState(topic_question="JB Hi-Fi returns", active_intent="policy", retailer="jb_hifi")
        decision = LocalController(lambda _: route("policy", "followup", "jb_hifi", "Kmart")).plan("What about Kmart?", state=state)
        self.assertEqual(decision["retailer"], "other")
        self.assertEqual(decision["action"], "clarify")
        self.assertIsNone(decision["provider"])

    def test_followup_topic_uses_only_user_question_as_search_context(self):
        state = ConversationState(topic_question="What is the title guarantee?", active_intent="law")
        controller = LocalController(lambda _: route("law", "followup"))
        decision = controller.plan("Explain it simply", [{"question":"What is the title guarantee?", "answer":"UNTRUSTED invented law"}], state)
        self.assertIn("What is the title guarantee?", decision["search_question"])
        self.assertIn("Explain it simply", decision["search_question"])
        self.assertNotIn("UNTRUSTED", decision["search_question"])

    def test_api_retains_topic_beyond_three_turns_and_fetches_fresh_policy(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        from test_retailer import fixture
        calls = []
        def fetcher():
            calls.append(1)
            return fixture()
        decisions = iter([route("tools", retailer="jb_hifi", mention="JB Hi-Fi")] + [route("policy", "followup")] * 5)
        controller = LocalController(lambda _: next(decisions))
        with patch("reg_assistant.api.load_pipeline") as load:
            with TestClient(create_app(controller=controller, policy_fetcher=fetcher)) as client:
                first = client.post("/api/ask", json={"question":"Have we added JB Hi-Fi support?"}).json()
                identifier = first["conversation_id"]
                for index in range(5):
                    response = client.post("/api/ask", json={"question":"warranties", "conversation_id":identifier,
                                                            "history":[{"question":"a recent question", "answer":"UNTRUSTED answer"}]})
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertEqual(result["conversation_id"], identifier)
                    self.assertEqual(result["policy_lookup"]["status"], "fetched")
                    self.assertEqual(result["conversation_state"]["topic_question"], "Have we added JB Hi-Fi support?")
                    self.assertNotIn("UNTRUSTED", result["answer"])
                    self.assertEqual(result["trace"]["session_turn"], index + 2)
            self.assertEqual(len(calls), 5)
            load.assert_not_called()

    def test_api_new_session_and_unknown_id(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        import uuid
        controller = LocalController(lambda _: route("clarify", reason="ambiguous"))
        with TestClient(create_app(controller=controller)) as client:
            first = client.post("/api/ask", json={"question":"unclear"}).json()
            followup = client.post("/api/ask", json={"question":"unclear", "conversation_id":first["conversation_id"]}).json()
            self.assertEqual(followup["trace"]["response_strategy"], "recovery")
            fresh = client.post("/api/ask", json={"question":"unclear"}).json()
            self.assertNotEqual(fresh["conversation_id"], first["conversation_id"])
            self.assertEqual(fresh["trace"]["response_strategy"], "clarify")
            self.assertEqual(client.post("/api/ask", json={"question":"q", "conversation_id":str(uuid.uuid4())}).status_code, 409)
            self.assertEqual(client.post("/api/ask", json={"question":"q", "conversation_id":"not-a-uuid"}).status_code, 422)

    def test_api_statutory_followup_passes_original_question_and_separate_search_context(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        decisions = iter([route("law"), route("law", "followup")])
        seen = []
        class Pipeline:
            def ask(self, question, **kwargs):
                seen.append((question, kwargs))
                return {"answer":"Source supported answer. [1]", "abstained":False, "evidence":[], "retrieved":[], "mode":"rag"}
        with TestClient(create_app(Pipeline(), controller=LocalController(lambda _: next(decisions)))) as client:
            first = client.post("/api/ask", json={"question":"What is the title guarantee?"}).json()
            client.post("/api/ask", json={"question":"Explain it simply", "conversation_id":first["conversation_id"]})
        self.assertEqual(seen[-1][0], "Explain it simply")
        self.assertIn("What is the title guarantee?", seen[-1][1]["search_question"])

    def test_current_message_first_never_passes_old_topic_to_standalone_router(self):
        import json
        seen=[]
        def generate(messages):
            seen.append(messages)
            return "STANDALONE" if messages[0]["content"].startswith("Classify the CURRENT") else route("models")
        controller=LocalController(generate)
        state=ConversationState(topic_question="JB Hi-Fi refunds",active_intent="policy",retailer="jb_hifi")
        result=controller.plan("Show the AI configuration",state=state)
        context=json.loads(seen[-1][-1]["content"])
        self.assertEqual(context["topic_state"],{})
        self.assertEqual(context["recent_user_questions"],[])
        self.assertEqual(result["fact_group"],"MODELS")
        state.advance("Show the AI configuration",result)
        self.assertEqual(state.retailer,"none")

    def test_topic_fragment_transitions_from_app_support_to_retailer_terms(self):
        def generate(messages):
            return "TOPIC" if messages[0]["content"].startswith("Classify the CURRENT") else route("tools","followup")
        state=ConversationState(topic_question="Have we enabled JB Hi-Fi support?",active_intent="tools",retailer="jb_hifi",turns=1)
        result=LocalController(generate).plan("warranties",state=state)
        self.assertEqual(result["action"],"policy")
        self.assertEqual(result["provider"],"jb_hifi")

    def test_new_shop_is_validated_even_if_dependency_classifier_calls_it_followup(self):
        def generate(messages):
            return "FOLLOWUP" if messages[0]["content"].startswith("Classify the CURRENT") else route("policy","followup","jb_hifi","Kmart")
        state=ConversationState(topic_question="JB Hi-Fi terms",active_intent="policy",retailer="jb_hifi",turns=1)
        result=LocalController(generate).plan("What about Kmart?",state=state)
        self.assertEqual(result["action"],"clarify")
        self.assertEqual(result["retailer"],"other")
        self.assertIsNone(result["provider"])

    def test_legal_topic_fragment_after_model_information_resets_search_anchor(self):
        state=ConversationState(topic_question="Which model powers this app?",active_intent="models",turns=3)
        def generate(messages):
            return "TOPIC" if messages[0]["content"].startswith("Classify the CURRENT") else route("law")
        controller=LocalController(generate)
        decision=controller.plan("Consequences of rejecting goods",state=state)
        self.assertEqual(decision["search_question"],"Consequences of rejecting goods")
        state.advance("Consequences of rejecting goods",decision)
        controller.generate=lambda messages: "FOLLOWUP" if messages[0]["content"].startswith("Classify the CURRENT") else route("law","followup")
        followup=controller.plan("Summarise that in plain English",state=state)
        self.assertIn("Consequences of rejecting goods",followup["search_question"])
        self.assertNotIn("model powers",followup["search_question"])

    def test_app_to_legal_to_summary_integration_has_fresh_evidence_without_client_history(self):
        from fastapi.testclient import TestClient
        from reg_assistant.api import create_app
        from test_rag import AnswerTests
        calls=[]
        def generate_answer(question,evidence,**kwargs):
            calls.append(question)
            return "Goods must meet the acceptable-quality guarantee. [1]"
        pipeline=AnswerTests().pipeline(.95,generate_answer)
        decisions=iter([route("models"),route("law"),route("law","followup")])
        with TestClient(create_app(pipeline,controller=LocalController(lambda _:next(decisions)))) as client:
            first=client.post("/api/ask",json={"question":"Which models are used?"}).json()
            law=client.post("/api/ask",json={"question":"What does section 54 say about acceptable quality?","conversation_id":first["conversation_id"]}).json()
            summary=client.post("/api/ask",json={"question":"Explain that in plain English","conversation_id":first["conversation_id"]}).json()
        self.assertFalse(law["abstained"])
        self.assertFalse(summary["abstained"])
        self.assertTrue(summary["evidence"])
        self.assertIn(summary["mode"],["plain-language","source-quotes"])
        self.assertNotIn("Which models",summary["trace"]["retrieval_query"])
        self.assertIn("section 54",summary["trace"]["retrieval_query"])
        self.assertEqual(len(calls),1)
