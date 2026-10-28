# Frozen experiment comparison

Synthetic section-disjoint questions. Source and citation checks do not measure factual correctness. Human factual/entailment review pending. End-to-end latency on one M3 Pro; first request includes cold loading.

| Pipeline | Source top 1 | Source top 3 | Supported answered | Unsupported declined | Median latency | Peak MLX |
| --- | --- | --- | --- | --- | --- | --- |
| [tfidf](test-tfidf.json) | 87.5% | 91.7% | 100.0% | 91.7% | 0.000 s | 0.00 GB |
| [hybrid](test-hybrid.json) | 91.7% | 95.8% | 87.5% | 100.0% | 0.395 s | 0.00 GB |
| [base-rag](test-base-rag.json) | 91.7% | 95.8% | 70.8% | 100.0% | 0.937 s | 1.77 GB |
| [adapter-rag](test-adapter-rag.json) | 91.7% | 95.8% | 83.3% | 100.0% | 0.966 s | 1.94 GB |

24 supported questions; 12 unsupported questions. Retrieval examines three chunks. The RAG evidence pack deduplicates sections and expands short provisions to their full text.

Extractive pipelines return passages without establishing answerability. A model response is accepted only when each paragraph ends in valid source references; rejected raw generations remain in the reports for inspection.

All generation uses the same prompt, retrieval settings and greedy decoding. The adapter ran 60 steps on 28 synthetic training examples. Selection of the local adapter was based on development behavior before the test comparison, not on test accuracy.

Latency includes CPU retrieval/reranking and MLX generation. Peak MLX allocation excludes CPU models and other applications. Cold first requests are marked in each report. Human review CSV files are intentionally ungraded.

Re-run commands and limitations are in [EXPERIMENTS.md](../EXPERIMENTS.md).
