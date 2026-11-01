# Free CPU semantic retrieval — 1 November 2026

The cloud profile uses pinned, quantized MiniLM embeddings and TF-IDF reciprocal
rank fusion. It loads no PyTorch, MLX, cross-encoder or LoRA adapter. Groq still
performs conversation routing and evidence-answer generation.

The [development regression](semantic-cpu-dev.json) passed 20/20 checks for
expected source presence or rejection without evidence. The cosine threshold
was selected using these development questions; this is not held-out accuracy.
Query processing measured about 5 ms median and 129 MiB peak process RSS on the
local macOS benchmark. A separate FastAPI test using the real retriever and
stub controller/generator peaked at 169 MiB. These measurements do not establish
Linux container memory usage, hosted-answer quality or total network latency.

Additional informal probes found limitations: “Can a business sell me something
it doesn't actually own?” and “What standard of workmanship should a paid service
meet?” did not clear the relevance gate. The refund/replacement probe retrieved
section 263; a request for a specific television's manufacturer coverage period
was rejected without evidence. No threshold changes were made from these probes.
Broader query interpretation and domain retrieval evaluation remain future work.

Reproduce locally in the Python 3.13 cloud environment:

```sh
pip install -r requirements-render.txt
python scripts/prepare_semantic_cpu.py
python scripts/check_semantic_cpu.py
```

The pinned model and generated index are ignored build artifacts. Their hashes,
the corpus fingerprint, vector dimensions/norms and chunk order are checked.
The existing citation-format validator still runs after hosted generation;
structurally valid citations do not prove factual support.
