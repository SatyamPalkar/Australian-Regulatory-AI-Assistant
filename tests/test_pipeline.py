import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from reg_assistant.core import ABSTENTION, Retriever, answer, build_index, chunk_documents, read_jsonl
from reg_assistant.ingest import MainText, ingest

ROOT = Path(__file__).resolve().parents[1]


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = read_jsonl(ROOT / "data/demo.jsonl")
        cls.retriever = Retriever(build_index(cls.documents))

    def test_retrieves_expected_source_and_preserves_provenance(self):
        result = answer("Does a warranty expiry end consumer guarantee rights?", self.retriever)
        self.assertEqual(result["evidence"][0]["id"], "accc-warranties")
        self.assertEqual(result["evidence"][0]["source_kind"], "curated_summary")
        self.assertTrue(result["evidence"][0]["url"].startswith("https://www.accc.gov.au/"))
        self.assertIn("[1]", result["answer"])

    def test_unrelated_question_abstains_without_loading_generator(self):
        def fail(*args):
            self.fail("Generator should not run without evidence")
        result = answer("Explain quantum chromodynamics", self.retriever, fail)
        self.assertEqual(result["answer"], ABSTENTION)
        self.assertEqual(result["evidence"], [])

    def test_rejects_missing_or_invented_citations(self):
        for text in ("A warranty is optional.", "A warranty is optional. [99]", "A warranty is optional. [0]"):
            with self.subTest(text=text):
                result = answer("Are extended warranties optional?", self.retriever, lambda *_: text)
                self.assertTrue(result["abstained"])
                self.assertFalse(result["citation_format_valid"])

    def test_accepts_explicit_model_abstention_despite_retrieval_match(self):
        result = answer("What exact penalty applies to consumer guarantees?", self.retriever,
                        lambda *_: ABSTENTION, min_score=0)
        self.assertTrue(result["abstained"])
        self.assertTrue(result["citation_format_valid"])

    def test_content_hash_changes_on_document_update(self):
        old = chunk_documents(self.documents)[0]["chunk_id"]
        updated = [{**self.documents[0], "text": self.documents[0]["text"] + " Additional guidance."}]
        self.assertNotEqual(old, chunk_documents(updated)[0]["chunk_id"])

    def test_chunks_overlap_without_losing_words(self):
        document = {**self.documents[0], "text": " ".join(str(i) for i in range(19))}
        chunks = chunk_documents([document], size=8, overlap=2)
        self.assertEqual([c["text"] for c in chunks],
                         ["0 1 2 3 4 5 6 7", "6 7 8 9 10 11 12 13", "12 13 14 15 16 17 18"])

    def test_rejects_duplicate_documents(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build_index([self.documents[0], self.documents[0]])


class IngestTests(unittest.TestCase):
    def test_excludes_navigation_scripts_and_footer(self):
        parser = MainText()
        parser.feed("<nav>outside</nav><main><h1>Title</h1><nav>menu</nav>"
                    "<p>Useful <strong>guidance</strong>.</p><script>ignore()</script>"
                    "</main><footer>outside</footer>")
        self.assertEqual(parser.text(), "Title\nUseful guidance.")

    def test_failed_download_preserves_existing_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "sources.json"
            manifest.write_text(json.dumps([{"id": "test", "url": "https://www.accc.gov.au/test"}]))
            output = root / "documents.jsonl"
            output.write_text("existing corpus")
            with patch("reg_assistant.ingest.urlopen", side_effect=HTTPError("https://www.accc.gov.au/test", 403, "Forbidden", {}, None)):
                with self.assertRaises(HTTPError):
                    ingest(manifest, output, root / "raw")
            self.assertEqual(output.read_text(), "existing corpus")

    def test_successful_download_saves_raw_hash_and_timestamp(self):
        raw = ("<html><main><p>" + "Useful guidance. " * 40 + "</p></main></html>").encode()
        class Headers(dict):
            def get_content_charset(self):
                return "utf-8"
        class Response:
            headers = Headers({"Content-Type": "text/html"})
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "https://www.accc.gov.au/test"
            def read(self, limit):
                return raw
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "sources.json"
            manifest.write_text(json.dumps([{"id": "test", "title": "Test", "url": "https://www.accc.gov.au/test"}]))
            with patch("reg_assistant.ingest.urlopen", return_value=Response()):
                self.assertEqual(ingest(manifest, root / "documents.jsonl", root / "raw"), 1)
            doc = read_jsonl(root / "documents.jsonl")[0]
            self.assertEqual(doc["source_kind"], "official_page")
            self.assertEqual(len(doc["sha256"]), 64)
            self.assertIn("retrieved_at", doc)
            self.assertEqual((root / "raw/test.html").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
