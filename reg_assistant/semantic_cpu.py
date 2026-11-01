"""Small CPU semantic + lexical retrieval. No Torch, MLX or cross-encoder."""
import hashlib
import json
import math
import re

from .core import Retriever, build_index, read_jsonl, write_json
from .rag import ROOT, RAGPipeline, statutory_search_query

INDEX = ROOT / "data/index-semantic-cpu.json"


def configuration():
    return json.loads((ROOT / "configs/semantic-cpu.json").read_text())


def config_digest(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def verify_file(path, expected):
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("CPU embedding asset missing or changed; run scripts/prepare_semantic_cpu.py")


class CPUEncoder:
    def __init__(self):
        spec = configuration()
        directory = ROOT / spec["path"]
        for name, metadata in spec["files"].items():
            verify_file(directory / name, metadata["sha256"])
        import onnxruntime as ort
        from tokenizers import Tokenizer
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=spec["max_length"])
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

    def encode(self, texts):
        import numpy as np
        vectors = []
        # One sequence at a time bounds activation memory even during indexing.
        for text in texts:
            item = self.tokenizer.encode(text)
            inputs = {"input_ids": np.array([item.ids], dtype=np.int64),
                      "attention_mask": np.array([item.attention_mask], dtype=np.int64),
                      "token_type_ids": np.array([item.type_ids], dtype=np.int64)}
            inputs = {entry.name: inputs[entry.name] for entry in self.session.get_inputs()}
            hidden = self.session.run(None, inputs)[0]
            mask = inputs["attention_mask"][..., None]
            pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
            pooled = pooled.astype(np.float32)
            norm = np.linalg.norm(pooled, axis=1, keepdims=True)
            if not np.isfinite(pooled).all() or (norm <= 0).any():
                raise RuntimeError("Invalid embedding output")
            vectors.append((pooled / norm)[0].tolist())
        return vectors


def build_semantic_index(documents, encoder, path=INDEX):
    lexical = build_index(documents)
    vectors = encoder.encode([c["text"] for c in lexical["chunks"]])
    result = {"version": 1, "config_sha256": config_digest(configuration()),
              "corpus_sha256": lexical["corpus_sha256"],
              "chunk_ids": [c["chunk_id"] for c in lexical["chunks"]], "vectors": vectors}
    validate_index(result, lexical)
    write_json(path, result)
    return result


def validate_index(dense, lexical):
    if (dense.get("version") != 1 or dense.get("config_sha256") != config_digest(configuration())
            or dense.get("corpus_sha256") != lexical["corpus_sha256"]
            or dense.get("chunk_ids") != [c["chunk_id"] for c in lexical["chunks"]]):
        raise RuntimeError("CPU semantic index is stale; rebuild it before serving")
    vectors = dense.get("vectors", [])
    dimensions = configuration()["dimensions"]
    if len(vectors) != len(lexical["chunks"]) or any(
            len(v) != dimensions or any(not math.isfinite(x) for x in v)
            or abs(sum(x*x for x in v) - 1) > .002 for v in vectors):
        raise RuntimeError("CPU semantic index has invalid vectors")


class SemanticCPURetriever:
    reranker_name = None

    def __init__(self, documents, encoder=None, dense=None):
        lexical = build_index(documents)
        dense = json.loads(INDEX.read_text()) if dense is None else dense
        validate_index(dense, lexical)
        self.lexical = Retriever(lexical)
        self.index = {**lexical, "backend": "semantic_cpu"}
        self.vectors = dense["vectors"]
        self.encoder = CPUEncoder() if encoder is None else encoder

    def search(self, question, k=3):
        if k < 1 or not question.strip():
            raise ValueError("Supply a nonempty question and a positive top-k")
        from .conversation import is_simplification_request
        topic, separator, followup = question.partition("\nCurrent follow-up: ")
        query = statutory_search_query(topic if separator and is_simplification_request(followup) else question)
        self.last_query = query
        embedding = self.encoder.encode([query])[0]
        if len(embedding) != configuration()["dimensions"] or not all(math.isfinite(x) for x in embedding):
            raise RuntimeError("Invalid query embedding")
        semantic = {c["chunk_id"]: sum(a*b for a, b in zip(embedding, v))
                    for c, v in zip(self.index["chunks"], self.vectors)}
        lexical = self.lexical.search(query, len(self.vectors))
        sparse = {c["chunk_id"]: c["score"] for c in lexical}
        dense_ranks = {key: rank for rank, key in enumerate(sorted(semantic, key=semantic.get, reverse=True), 1)}
        sparse_ranks = {c["chunk_id"]: rank for rank, c in enumerate(lexical, 1) if c["score"] > 0}
        requested = re.findall(r"\b(?:section|s\.)\s*(\d+[a-z]?)\b", question.lower())
        hits = []
        for chunk in self.index["chunks"]:
            if requested and chunk.get("section_number", "").lower() not in requested:
                continue
            key = chunk["chunk_id"]
            eligible = semantic[key] >= configuration()["semantic_min_score"]
            rrf = 1 / (60 + dense_ranks[key])
            if key in sparse_ranks:
                rrf += 1 / (60 + sparse_ranks[key])
            hits.append({**chunk, "score": round(semantic[key], 6), "lexical_score": sparse[key],
                         "fusion_score": round(rrf, 8), "eligible": eligible})
        # Admission is a relevance heuristic, never a factual-confidence score.
        unique, seen = [], set()
        for hit in sorted(hits, key=lambda h: (h["eligible"], h["fusion_score"]), reverse=True):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                unique.append(hit)
        return unique[:k]


def load_semantic_cpu_pipeline(generator):
    return RAGPipeline(SemanticCPURetriever(read_jsonl(ROOT / "data/consumer_law.jsonl")),
                       generator, min_score=-1)
