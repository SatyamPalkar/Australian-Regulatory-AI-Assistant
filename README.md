# Australian regulatory assistant

A local project for an Apple Silicon Mac: retrieve Australian regulatory guidance,
show source-linked evidence, then compare a base language model against an MLX LoRA
adapter using the same retrieval index and questions.

The first slice covers ACCC consumer guarantees, warranties and remedies. This is
a research prototype for general guidance, not personalised legal advice.

## Web interface and deployment

[Open the deployed demo](https://australian-regulatory-ai-assistant.snowybead1.chatgpt.site)
(owner-private; sign in with your ChatGPT account).

The `site/` web application includes an assistant, a source library, cited passages,
copy/export controls and the saved evaluation results. A same-origin backend serves
the retrieval API. Its search results are tested against the Python baseline.
See [DEPLOYMENT.md](DEPLOYMENT.md) for local setup, API details, verification,
the Sites deployment workflow and the distinction between hosted retrieval and
Apple Silicon model inference.

```sh
cd site
npm run install:ci
npm run dev
```

Open `http://localhost:5173` (Node.js 24 required).

## Current status

The dependency-free command-line demo works with three **curated summaries**, not
full official documents. Each summary identifies its official source and verification
date. Direct ACCC downloads returned HTTP 403 in the development environment.
The importer is implemented and tested with HTTP fixtures; successful live ingestion
still needs verification on a network that can access the pages.

The default retrieval baseline is **TF-IDF**, not semantic embeddings. Default answers
display retrieved passages with citations; they do not synthesise an LLM answer.
Optional semantic retrieval and local MLX generation are implemented but have not
been exercised with downloaded model weights. No fine-tuning or memory benchmark
has been run. See `reports/dev-baseline.json` for measured baseline results.
Ten automated tests passed for retrieval, provenance, chunking, citation rejection,
and ingestion success/failure handling. The six supported development questions
retrieved the expected source first; two of three unsupported questions triggered
abstention. With only three documents, hit-at-three is a trivial metric, so the
report also includes hit-at-one. These results are a smoke check, not evidence of
general regulatory accuracy.

## Run the working demo

From this directory, with Python 3.9 or later, no installation or network is needed:

```sh
python3 -m reg_assistant.cli index
python3 -m reg_assistant.cli ask "Do consumer guarantee rights end when a warranty expires?"
python3 -m reg_assistant.cli ask "What documents do I need for a student visa?"
python3 -m reg_assistant.cli evaluate
python3 -m unittest discover -s tests -v
```

Run `python3 -m reg_assistant.cli --help` for commands. Pass `--json` to `ask` for
scores, evidence, citation checks and abstention state. Paths are relative to the
working directory; `--index`, `--documents` and `--questions` accept other paths.

## Use full official pages

```sh
python3 -m reg_assistant.cli ingest
python3 -m reg_assistant.cli index --documents data/documents.jsonl --output data/index-official.json
python3 -m reg_assistant.cli ask "What counts as acceptable quality?" --index data/index-official.json
```

The explicit manifest is `data/sources.json`. The importer saves raw HTML, SHA-256,
the final URL and a UTC retrieval timestamp. It extracts `<main>` text, omits scripts
and navigation, and preserves the old corpus if any download fails. Review extracted
text before indexing: layouts and guidance can change. A retrieval timestamp is not
an effective date or a guarantee that the guidance is current. This importer handles
HTML only; PDF extraction is a future extension.

## Enable local models

Use Python 3.11+ on Apple Silicon for the optional stack. Install it in an isolated
environment; the first use downloads dependencies and public model weights.

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[semantic,mlx]'
python -m reg_assistant.cli index --backend semantic --output data/index-semantic.json
python -m reg_assistant.cli ask "What happens after a manufacturer's warranty expires?" --index data/index-semantic.json --generator mlx
python -m reg_assistant.cli evaluate --index data/index-semantic.json --generator mlx --output reports/dev-mlx.json
```

Add `--documents data/documents.jsonl` to index full pages instead of the demo.
The embedding model is [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
which produces 384-dimensional vectors. Embeddings run locally on CPU to keep
the implementation portable. The default generator is the
[MLX Qwen2.5 1.5B 4-bit model](https://huggingface.co/mlx-community/Qwen2.5-1.5B-Instruct-4bit).
Use `--model` to select a compatible repository or local path. After caching the
models, `HF_HUB_OFFLINE=1` prevents Hugging Face network lookups.

The optional dependency ranges are initial compatibility constraints, not a tested
lockfile. Record a successful environment with `python -m pip freeze > reports/environment.txt`
after validating the optional stack. Model revisions should also be pinned for a
final comparison.

## Evaluation and limits

`eval/dev.jsonl` contains six supported and three unsupported development questions.
This small, inspected set is **not** a final held-out test set. Reports preserve index,
corpus and question hashes, configuration, answers, passages and per-question latency.

Metrics include source retrieval hit at k, expected source citations, unsupported
abstentions, and reference syntax. Source presence and correct citation numbers do
not establish that a claim is supported. Human review must score factual correctness,
claim-to-evidence support, missing qualifications and useful abstentions. The extractive
baseline will sometimes retrieve related passages for an unanswerable question;
the exact-penalty development question intentionally exposes that limitation.

Retrieval thresholds default to 0.16 for TF-IDF and 0.40 for semantic cosine similarity.
These are starting values, not calibrated confidence scores. Tune on development data
only. Model prompts request evidence-based abstention. Invalid or missing numerical
references trigger abstention, but valid references can still accompany unsupported
claims. The code checks reference syntax and range, not semantic entailment.

## Next milestones

1. Verify full-page ingestion and semantic retrieval; record a base-model RAG run.
2. Create reviewed training examples containing a question, retrieved evidence,
   a cited answer or an explicit abstention. Include misleading and insufficient
   evidence. Group splits by source section and question family to avoid paraphrase
   leakage. Keep the retrieval corpus available to both evaluation variants.
3. Freeze a separate held-out question set before training. Never use it for example
   generation, threshold selection or model selection.
4. Benchmark ten QLoRA steps with `configs/lora-smoke.yaml`, then scale only after
   measuring memory pressure, peak process/GPU memory, sequence length and throughput.
   Start with batch size one, sequence length 256, four adapted layers and rank four.
5. Compare base RAG with adapter RAG on the same index, prompts, decoding settings and
   questions. Report human groundedness scores alongside retrieval, latency and memory.

The smoke configuration is a **template**, requiring reviewed `data/training/train.jsonl`
and `valid.jsonl`; those datasets are deliberately not generated from evaluation rows.
With the training extra installed, run:

```sh
python -m pip install 'mlx-lm[train]'
mlx_lm.lora --config configs/lora-smoke.yaml
python -m reg_assistant.cli evaluate --index data/index-semantic.json --generator mlx --adapter adapters/smoke --output reports/dev-adapter.json
```

MLX supports LoRA on quantized weights (QLoRA); see its
[fine-tuning documentation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
and [configuration example](https://github.com/ml-explore/mlx-lm/blob/main/examples/lora_config.yaml).
The smoke run measures feasibility, not model improvement. Available unified memory
and competing applications must be measured on the actual Mac before choosing a
larger workload.

## Corpus references

- [ACCC: Consumer rights and guarantees](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees)
- [ACCC: Warranties](https://www.accc.gov.au/consumers/buying-products-and-services/warranties)
- [ACCC: Repair, replace, refund, cancel](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/repair-replace-refund-cancel)

The bundled summaries are project-authored paraphrases verified on 28 October 2026.
They are a narrow demo corpus, omit qualifications, and are not an official ACCC
publication or a substitute for the linked guidance. Recheck originals before use.
