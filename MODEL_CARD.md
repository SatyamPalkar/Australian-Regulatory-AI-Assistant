# Local model card

## Intended use

A portfolio research assistant for finding and summarising selected Australian
Consumer Law provisions with inspectable citations. The assistant uses a pinned
27 August 2026 snapshot, not a complete or guaranteed-current legal collection.
It is not validated for case outcomes, legal advice, filing fees or deadlines not
present in the evidence.

## Components

| Role | Model | Licence |
| --- | --- | --- |
| Embeddings | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Apache 2.0 |
| Reranker | [ms-marco-MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) | Apache 2.0 |
| Generator | [Qwen2.5-1.5B-Instruct, MLX four-bit conversion](https://huggingface.co/mlx-community/Qwen2.5-1.5B-Instruct-4bit) | Apache 2.0 |

Immutable revisions are in `configs/models.json`; model cards/licences are retained
with downloaded snapshots. Statutory data attribution and CC BY 4.0 transformation
details are separate in `data/ATTRIBUTION.md`. Training examples are synthetic
derivatives of that corpus and keep the same attribution requirements.

The adapter has approximately 0.659 million trainable parameters (0.043% of the
base model), rank four across four layers, and was trained for 60 steps on 28
examples. Prompt tokens were masked. One source per supported training example
means complex multi-source reasoning is not represented well. Validation examples
share topics with training and are not an independent test.

## Behaviour and limits

The assistant retrieves, reranks, supplies evidence to the model, and enforces
paragraph-level reference syntax. It can abstain because retrieval found weak
evidence, because the model declined, or because output references failed checks.
Valid citation syntax does not prove factual support. The model can misread
exceptions, omit qualifications, or overgeneralise from a short passage. Prompt
injection examples were tested on a small synthetic set; this is not a security
guarantee. Source text and questions are treated as data in the prompt.

The hosted GitHub Pages version performs lexical retrieval and shows saved model
results. Actual MLX generation requires the local Mac API. The local API is bound
to loopback, serialises model requests, and has input limits. It is not an
authenticated, rate-limited public inference service. No question history is
persisted by the API; frontend research exports are explicitly downloaded by the
visitor. Server console logs contain paths/status codes, not question bodies.

## Evaluation and selection

[EXPERIMENTS.md](EXPERIMENTS.md) records the procedure, fixed settings, failure
analysis and pending human review. The adapter was chosen using development
behaviour before the test comparison. Test source sections are disjoint from
training evidence, but related legal topics overlap and pretraining contamination
was not assessed. All questions were authored during implementation and have not
received independent legal review. No factual-accuracy claim is made.

On 24 supported test questions, base RAG returned 17 accepted cited answers and
adapter RAG returned 20. Both declined the 12 unsupported questions. These results
are limited to this small test and include the effects of retrieval and structural
output rejection. See the saved raw reports for counterexamples.

## Second adapter and conversation context

The phase-two adapter is experimental and remains opt-in. It learned longer
Rule/Meaning/Limits responses from 64 synthetic examples, but source checks found
misstatements despite better structural scores. It was not promoted to default.
The local API accepts bounded recent history; default dependent follow-ups quote
fresh source text because live checks found qualification errors in generative
follow-ups as well. Standalone concise answers retain the original model's known
limitations. See [PHASE2.md](PHASE2.md) for data provenance, measurements, review
findings, exact history limits and reproduction.
