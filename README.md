# Australian Regulatory AI Assistant

A dark chatbot interface and local Python retrieval pipeline over real Australian
consumer-law text. The active corpus contains **37 statutory sections**, indexed
as **93 passages**, from Schedule 2 of the Competition and Consumer Act 2010.

[Open the deployed application](https://australian-regulatory-ai-assistant.snowybead1.chatgpt.site)
(owner-private; sign in with your ChatGPT account).

## Real dataset and Sydney coverage

The statutory text comes from [cchew/lex-au on Hugging Face](https://huggingface.co/datasets/cchew/lex-au),
an Akoma Ntoso XML conversion of Commonwealth legislation. The import is pinned to
revision `ce532ddeb514fa477d6466a892fa17e62d21513e`; both downloaded files are checked
against SHA-256 hashes. The source compilation is **C2026C00389, 27 August 2026**.

The collection covers consumer guarantees, misleading conduct, unfair contract
terms, repairs and refunds, and remedies against suppliers and manufacturers.
These are selected national consumer-law provisions relevant to Sydney and NSW.
State-only Acts, council by-laws, tribunal fees and practical complaint-handling
guidance are outside the collection.

The official register listed a newer Act compilation, **C2026C00405, 16 September
2026**, when checked on 28 October 2026. Changes to the selected sections have not
been compared. The app labels the dataset snapshot and links to the official law.

Copyright remains with the Commonwealth of Australia. The dataset is distributed
under CC BY 4.0. This project selects sections, removes XML markup, normalises
whitespace and adds retrieval metadata. See [data/ATTRIBUTION.md](data/ATTRIBUTION.md).
The separate `data/demo.jsonl` retains the original authored ACCC summaries for
historical tests; those summaries are not the active hosted corpus.

## Run locally

Python 3.9+ is sufficient; the statutory extract is bundled and no installation or
network is required for the lexical baseline. Run from this directory:

```sh
python3 -m reg_assistant.cli index
python3 -m reg_assistant.cli ask "What guarantee applies to services supplied with due care and skill?"
python3 -m reg_assistant.cli evaluate
python3 -m unittest discover -s tests -v
```

The default documents are `data/consumer_law.jsonl`. Evaluation uses
`eval/consumer-law-dev.jsonl` and writes `reports/consumer-law-baseline.json`.
Use `ask --json` to inspect source metadata and retrieval scores.

To reproduce the import from Hugging Face, including its raw source files:

```sh
python3 scripts/import_huggingface.py
python3 -m reg_assistant.cli index
python3 -m reg_assistant.cli evaluate
python3 scripts/export_site_data.py
```

The importer uses `data/huggingface_sources.json`, caches pinned files under ignored
`data/raw/huggingface/`, and replaces the corpus only after checksums, law-version
metadata and every selected section have been verified. A new dataset revision
requires a reviewed manifest update with new checksums and a fresh evaluation.

## Browser interface

Node.js 24 is required:

```sh
cd site
npm run install:ci
npm run dev
```

Open `http://localhost:5173`. The interface includes cited passages, a searchable
statutory section library, version/licence details, research exports and the saved
development evaluation. The hosted Worker uses the exported Python TF-IDF index;
parity tests compare its outputs with Python. It does not run an LLM or adapter.
See [DEPLOYMENT.md](DEPLOYMENT.md) for API, build, browser QA and publication details.

## Evaluation and limits

The development set contains nine supported and three unsupported questions.
The expected section was first for **7/9**, within the top three for **9/9**, and
**2/3** unsupported questions triggered abstention. The visa question is a known
answerability failure. This inspected set is not a held-out test or a legal
accuracy benchmark.

The app displays retrieved statutory passages with citations. It does not decide
legal outcomes. Source presence, keywords and valid citation numbers do not prove
that a passage answers a question or that a conclusion is legally correct.
Qualifying subsections can occur outside a retrieved chunk: always consult the
complete provision and its current official version.

TF-IDF uses a 0.16 similarity threshold and a minimum 0.5 vocabulary-coverage scope
heuristic to reduce relevance inflation from unknown query terms. These are
development settings, not calibrated confidence scores. Semantic mode starts at
0.40 cosine similarity. Tune only on development data.

The exporter refuses a mismatched corpus, changed questions, or an evaluation with
answers that differ from the current retrieval behavior. The GitHub CI workflow
checks deterministic exports, Python/web tests, types and the production build.

## Optional local models and later fine-tuning

Use Python 3.11+ on Apple Silicon for the optional model stack:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[semantic,mlx]'
python -m reg_assistant.cli index --backend semantic --output data/index-semantic.json
python -m reg_assistant.cli ask "What does the law say about acceptable quality?" --index data/index-semantic.json --generator mlx
```

The configured models are `sentence-transformers/all-MiniLM-L6-v2` and
`mlx-community/Qwen2.5-1.5B-Instruct-4bit`. Model downloads, semantic inference and
MLX inference remain unverified here. The optional dependency ranges are not a
validated lockfile. No fine-tuning or memory benchmark has been performed.

`configs/lora-smoke.yaml` is a template for ten QLoRA steps with batch size one,
sequence length 256, four adapted layers and rank four. It requires reviewed
`data/training/train.jsonl` and `valid.jsonl`. Build training examples from evidence,
keep question families separated, and freeze an independent held-out set before
training. Compare base RAG and adapter RAG on identical retrieval and decoding
settings, with human evidence-support review plus latency and memory measurements.

For the historical summary baseline, explicitly select `data/demo.jsonl`,
`eval/dev.jsonl` and a separate report path. `reports/dev-baseline.json` records the
earlier summary run and should not be read as current statutory-corpus performance.
