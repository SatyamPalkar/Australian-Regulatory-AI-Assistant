import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate_routing_boundary import DEFAULT_MANIFEST, validate_manifest, validate_rows


def case(identifier, question, family="scenario-a", category="consumer_law", intent="law"):
    action = "statutory" if intent == "law" else "chat"
    expectation = "retrieve_evidence_or_explain_coverage_limit" if category == "consumer_law" else "runtime_facts_only"
    return {"id":identifier,"family":family,"turns":[{"question":question,"category":category,"intents":[intent],
            "actions":[action],"answer_expectation":expectation,"forbid_policy":True}]}


class RoutingBoundaryTests(unittest.TestCase):
    def test_frozen_suite_is_balanced_and_does_not_call_the_model(self):
        with patch("reg_assistant.assistant.LocalController.complete", side_effect=AssertionError("Do not consume held-out cases")):
            result = validate_manifest()
        self.assertEqual(result["splits"]["dev"]["turns"],32)
        self.assertEqual(result["splits"]["holdout"]["turns"],32)
        self.assertEqual(result["contrast_pairs"],8)
        categories = {}
        for split in result["splits"].values():
            for category,count in split["categories"].items(): categories[category] = categories.get(category,0)+count
        self.assertEqual(categories["consumer_law"],categories["app_information"])

    def test_legal_question_cannot_be_labelled_with_app_action(self):
        row = case("one","Explain warranty rights")
        row["turns"][0]["actions"] = ["chat"]
        with self.assertRaisesRegex(ValueError,"action/intent"):
            validate_rows({"dev":[row],"holdout":[]})

    def test_scenario_family_cannot_cross_splits(self):
        with self.assertRaisesRegex(ValueError,"family crosses"):
            validate_rows({"dev":[case("one","Explain a refund remedy")],
                           "holdout":[case("two","Explain a different refund remedy")]})

    def test_case_and_punctuation_changes_do_not_hide_duplicate_questions(self):
        with self.assertRaisesRegex(ValueError,"Duplicate question"):
            validate_rows({"dev":[case("one","Explain refund rights!")],
                           "holdout":[case("two","EXPLAIN refund rights?",family="another")]})

    def test_existing_regression_or_prompt_questions_cannot_be_claimed_as_fresh(self):
        row = case("one","Explain warranty rights")
        for options in [{"regression_questions":["Explain warranty rights."]},
                        {"prompts":["An example asks: Explain warranty rights."]}]:
            with self.subTest(options=options),self.assertRaises(ValueError):
                validate_rows({"dev":[row],"holdout":[]},**options)

    def test_contrast_pair_must_include_both_legal_and_app_questions(self):
        rows = [case("one","Explain warranties"),case("two","Explain refunds")]
        for row in rows: row["contrast_pair"] = "same-words"
        with self.assertRaisesRegex(ValueError,"contrast pair"):
            validate_rows({"dev":rows,"holdout":[]})

    def test_retaining_old_user_search_context_requires_an_actual_earlier_question(self):
        row = case("one","Explain warranty rights")
        row["turns"][0]["search_contains"] = "made-up earlier topic"
        with self.assertRaisesRegex(ValueError,"search anchor"):
            validate_rows({"dev":[row],"holdout":[]})

    def test_accidental_dataset_edit_is_detected_by_manifest_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)
            target=parent/"routing-boundary"
            shutil.copytree(DEFAULT_MANIFEST.parent,target)
            manifest=json.loads(DEFAULT_MANIFEST.read_text())
            source=(DEFAULT_MANIFEST.parent/manifest["regression_set"]).resolve()
            shutil.copy2(source,parent/source.name)
            validate_manifest(target/"manifest.json")
            with (target/"dev.jsonl").open("a") as stream: stream.write("\n")
            with self.assertRaisesRegex(ValueError,"Dataset hash changed"):
                validate_manifest(target/"manifest.json")
