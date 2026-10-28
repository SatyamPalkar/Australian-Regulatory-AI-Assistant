import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reg_assistant.huggingface import checked_bytes, download_file, extract_sections, import_huggingface

XML = b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta>
<identification><FRBRExpression><FRBRdate date="2026-08-27"/></FRBRExpression></identification></meta>
<attachments><attachment><hcontainer name="schedule" eId="schedule-1"><heading>Other law</heading>
<hcontainer name="clause" eId="other-54"><num>54</num><heading>Wrong provision</heading><content>Do not select this text.</content></hcontainer>
</hcontainer></attachment><attachment><hcontainer name="schedule" eId="schedule-2"><heading>The Australian Consumer Law</heading>
<hcontainer name="clause" eId="schedule-2__clause-54"><num>54</num><heading>Guarantee as to acceptable quality</heading>
<content><p>Goods must be of acceptable quality and must be safe and durable.</p></content></hcontainer>
</hcontainer></attachment></attachments></act></akomaNtoso>'''
INDEX = {"acts": {"test": {"effective_date": "2026-08-27", "name": "Competition and Consumer Act 2010", "title_id": "C2004A00109", "comp_id": "C2026C00389"}}}
MANIFEST = {"dataset": "cchew/lex-au", "revision": "a" * 40, "slug": "test", "index_file": "index.json", "xml_file": "law.xml", "xml_sha256": hashlib.sha256(XML).hexdigest(), "schedule": "schedule-2", "sections": ["54"], "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"}


class HuggingFaceTests(unittest.TestCase):
    def test_extracts_the_requested_schedule_and_preserves_provenance(self):
        document = extract_sections(XML, INDEX, MANIFEST, "2026-10-28T00:00:00+00:00")[0]
        self.assertEqual(document["id"], "acl-s54")
        self.assertIn("safe and durable", document["text"])
        self.assertNotIn("Wrong provision", document["text"])
        self.assertEqual(document["source_kind"], "legislation_extract")
        self.assertEqual(document["compilation_id"], "C2026C00389")
        self.assertEqual(document["dataset_revision"], "a" * 40)
        self.assertEqual(document["license"], "CC-BY-4.0")

    def test_rejects_mismatched_law_version(self):
        index = copy.deepcopy(INDEX)
        index["acts"]["test"]["effective_date"] = "2020-01-01"
        with self.assertRaisesRegex(ValueError, "version"):
            extract_sections(XML, index, MANIFEST, "now")

    def test_missing_or_duplicate_selected_sections_fail(self):
        for sections in (["99"], ["54", "54"]):
            with self.assertRaises(ValueError):
                extract_sections(XML, INDEX, {**MANIFEST, "sections": sections}, "now")

    def test_changed_source_bytes_fail_checksum(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            checked_bytes(XML + b"changed", MANIFEST["xml_sha256"])

    def test_import_requires_immutable_revision_even_with_cache(self):
        with self.assertRaisesRegex(ValueError, "revision"):
            download_file("cchew/lex-au", "main", "law.xml", MANIFEST["xml_sha256"], ".")

    def test_failed_import_keeps_existing_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({**MANIFEST, "index_sha256": "0" * 64}))
            (root / "corpus.jsonl").write_text("previous corpus")
            with patch("reg_assistant.huggingface.download_file", side_effect=ValueError("checksum mismatch")):
                with self.assertRaises(ValueError):
                    import_huggingface(root / "manifest.json", root / "corpus.jsonl", root / "cache")
            self.assertEqual((root / "corpus.jsonl").read_text(), "previous corpus")


if __name__ == "__main__":
    unittest.main()
