"""Small public-demo retriever; no embeddings, reranker, Torch or MLX imports."""
import re
from .core import (MIN_QUERY_COVERAGE, Retriever, build_index, query_coverage,
                   read_jsonl)
from .rag import ROOT, RAGPipeline, statutory_search_query


class LexicalEvidenceRetriever:
    reranker_name = None

    def __init__(self, documents):
        self.index = build_index(documents)
        self.lexical = Retriever(self.index)

    def search(self, question, k=3):
        from .conversation import is_simplification_request
        topic, separator, followup = question.partition("\nCurrent follow-up: ")
        # Wording-only follow-ups should not dilute the legal topic with style
        # terms and spelling variants in a vocabulary-based retriever.
        search_question = topic if separator and is_simplification_request(followup) else question
        query = statutory_search_query(search_question)
        self.last_query = query
        requested = re.findall(r"\b(?:section|s\.)\s*(\d+[a-z]?)\b", question.lower())
        hits = self.lexical.search(query, len(self.index["chunks"]) if requested else k)
        if requested:
            hits = [hit for hit in hits if hit.get("section_number", "").lower() in requested][:k]
        if query_coverage(query, self.index["idf"]) < MIN_QUERY_COVERAGE:
            return [{**hit, "score": 0.0} for hit in hits]
        return hits


def load_lexical_pipeline(generator):
    documents = read_jsonl(ROOT / "data/consumer_law.jsonl")
    return RAGPipeline(LexicalEvidenceRetriever(documents), generator, min_score=.16)
