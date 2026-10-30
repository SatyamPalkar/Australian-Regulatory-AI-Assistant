# Australian Regulatory AI Assistant

Version **0.3.0** adds optional Groq-hosted inference and evaluated conversation
routing. The public GitHub Pages application remains a browser retrieval demo;
the model-backed Python API runs separately.

A local, model-backed research assistant with hybrid retrieval, reranking, cited
MLX answers, a measured LoRA experiment, and a dark chatbot interface. The active corpus contains **37 statutory sections**, indexed
as **93 passages**, from Schedule 2 of the Competition and Consumer Act 2010.

[Open the GitHub Pages application](https://satyampalkar.github.io/Australian-Regulatory-AI-Assistant/).
The public Pages version searches the bundled corpus entirely in your browser and
shows the saved model experiment. Run the local API for actual LLM generation.

## Measured on an M3 Pro

The frozen synthetic test contains 24 supported and 12 unsupported questions. Its
source sections are disjoint from the training sections; it is not an independently
reviewed legal benchmark.

| Pipeline | Expected source in top 3 | Supported questions answered | Unsupported questions declined |
| --- | --- | --- | --- |
| TF-IDF passages | 22/24 | 24/24 passages returned | 11/12 |
| Hybrid + reranker passages | 23/24 | 21/24 passages returned | 12/12 |
| Base Qwen + RAG | 23/24 | 17/24 cited answers | 12/12 |
| LoRA Qwen + RAG | 23/24 | 20/24 cited answers | 12/12 |

A response passing citation checks is **not a verified correct answer**. The small
LoRA experiment improved response acceptance on this test; factual correctness and
citation entailment remain ungraded. Median LoRA RAG latency was 0.97 seconds and
peak MLX allocation was 1.94 GB. The 60-step training run took 49.6 seconds with
2.32 GB peak MLX allocation. These figures describe one machine and experiment.

[Full comparison and failures](reports/comparison.md) · [Experiment protocol](EXPERIMENTS.md) · [Model card](MODEL_CARD.md)

## Run the model-backed app on your Mac

Tested with Python 3.13, macOS 15.6.1, Apple M3 Pro and 18 GB unified memory.
Model downloads including the separate controller total approximately 3.34 GB.
The default local profile needs no paid API or API key.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-macos.lock
python scripts/download_models.py
python scripts/download_controller.py
python -m reg_assistant.cli index --backend hybrid --output data/index-hybrid.json
python scripts/train_lora.py --smoke
python scripts/train_lora.py
cd site
npm run install:ci
npm run build:pages
cd ..
python -m reg_assistant.cli serve
```

Open **http://127.0.0.1:8000/Australian-Regulatory-AI-Assistant/**. The local server
selects hybrid retrieval and the trained adapter automatically. Use `serve
--base-model` to compare the unadapted model. The server binds to loopback and
processes one question at a time; it is a local research service.

For optional hosted inference, store `GROQ_API_KEY` in the server environment or
an ignored root `.env` file (see `.env.example`), then run:

```sh
python -m reg_assistant.cli serve --provider groq
```

This profile uses the Groq-hosted model selected in `configs/groq.json` for both
routing and evidence answers. It sends questions, bounded conversation context
and retrieved evidence to Groq. Embeddings and reranking remain local. It does
not load the local language models or your LoRA adapter; existing retrieval,
session and structural citation checks still apply. The UI labels this profile
as Groq. API limits/errors remain visible; there is no silent local fallback.
Free-tier availability and quotas are provider-controlled. This command still
runs the Python server on your Mac; it does not deploy a public backend.

[Groq validation results and limits](reports/groq-validation.md): 32/32 development
routing checks, 22/22 conversation regression turns and 7/7 full-path API checks.
These checks do not establish legal factual accuracy.

The trained adapter and model weights stay outside Git. Anyone cloning the repo
can reproduce them with the commands above. Existing adapters are protected from
accidental overwrite. The dependency snapshot is specific to the tested Mac stack;
the lightweight TF-IDF baseline below still runs with Python 3.9 and no packages.

```mermaid
flowchart LR
    Q[Question] --> H[Lexical + dense retrieval]
    H --> F[Reciprocal rank fusion]
    F --> R[Cross-encoder reranker]
    R --> E[Full short sections + provenance]
    E --> M[Qwen 1.5B four-bit + LoRA]
    M --> C[Per-paragraph citation checks]
    C --> A[Cited answer or abstention]
```

## Conversation context and the next experiment

The local AI accepts up to three recent turns within a 6,000-character history
budget, plus bounded server-side topic state, and retrieves fresh evidence for follow-ups. The default profile quotes
fresh statutory wording for dependent follow-ups. Requests to simplify a previous
answer can use prepared, source-version-pinned plain-language guides for eight
common sections; these are labelled guides rather than model-generated text. The original concise adapter
handles standalone questions. The browser-only demo still handles questions
independently.

A second adapter trained on 64 explanatory/conversation examples in 145.1 seconds
with 2.47 GB peak MLX allocation. On its 16-question synthetic test it produced
three-part cited explanations for 6/10 supported questions, versus 0/10 for the
original adapter under the same explanatory prompt; both declined 6/6 unsupported
questions. **Source review found factual errors, so the new adapter was not promoted.**
Structure/keyword improvements are not verified answer accuracy.

[Phase-two protocol and local commands](PHASE2.md) · [Results and failures](reports/phase2-comparison.md)

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
npm run build:pages
npm run preview:pages
```

Open `http://127.0.0.1:4174/Australian-Regulatory-AI-Assistant/`. The interface includes cited passages, a searchable
statutory section library, version/licence details, research exports and the saved
development evaluation. GitHub Pages runs the same TF-IDF engine locally in the
browser; questions require no backend or API keys. Pushes to `main` trigger the
Pages build and deployment workflow. GitHub Pages itself does not run an LLM or adapter.
The mode control can connect a running API; the same-origin local URL above is the
recommended model-backed experience. Browser security policies may restrict remote
Pages-to-localhost connections.

The optional Worker deployment and its API remain supported: `npm run dev` serves
that variant at `http://localhost:5173`. See [DEPLOYMENT.md](DEPLOYMENT.md) for both
hosting targets, browser QA and publication details.

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

## Model stack and reproducibility

The new hybrid pipeline uses the pinned models in `configs/models.json`:

- `sentence-transformers/all-MiniLM-L6-v2` for dense retrieval, combined with TF-IDF
  through reciprocal rank fusion over 12 candidates.
- `cross-encoder/ms-marco-MiniLM-L6-v2` for relevance reranking and a 0.5 sigmoid
  threshold. This threshold is a development setting, not answer confidence.
- `mlx-community/Qwen2.5-1.5B-Instruct-4bit` for greedy generation, capped at 256
  output tokens, with optional four-layer rank-four LoRA adapters.

CPU embedding/reranking uses float64 and eager attention because float32 CPU
reranker inference produced NaNs on the tested setup. Non-finite embeddings or
reranker scores cause an error. Short source sections are expanded in full to
preserve qualifications; long sections remain visibly partial evidence. Each
answer paragraph must end with valid supplied reference numbers. This structural
check cannot establish entailment or prevent every hallucination.

```sh
python scripts/run_experiment.py --suite test --modes tfidf hybrid base-rag adapter-rag
python scripts/export_experiments.py
python -m unittest discover -s tests -v
```

The checked-in 36-question test is now observed. Further tuning must use development
data; future independent claims need a new frozen test. See `EXPERIMENTS.md` for
split hashes, training logs, failure analysis and the pending human-review rubric.

For the historical summary baseline, explicitly select `data/demo.jsonl`,
`eval/dev.jsonl` and a separate report path. `reports/dev-baseline.json` records the
earlier summary run and should not be read as current statutory-corpus performance.

### Official retailer-policy context

The local API uses the local instruction model to interpret each question and recent conversation before choosing conversation, clarification, statutory retrieval, or an available policy tool. It no longer uses retailer keywords as its local API intent gate. The policy tool currently supports JB Hi-Fi returns, refunds and warranties. It reads the official help centre’s public article endpoint and returns dated, cited policy excerpts, preserving Marketplace exclusions and category-specific table conditions. It asks whether the product is faulty or a change-of-mind return and requests purchase details. The policy fetch itself requires no API key; the local conversation controller uses the installed instruction model. Questions/history are not sent to the retailer.

Try: **“What is JB Hi-Fi’s return policy?”**, then **“I opened it; can I return it?”**. The retailer registry currently supports JB Hi-Fi only. Lookup failure produces an explicit unverified-policy message with the official link and a useful clarification. The statutory corpus and saved evaluations are unchanged.

GitHub Pages alone cannot fetch the retailer’s cross-origin-restricted content: connect the local API using the existing connection settings for live lookup. The server-hosted web API also supports online lookup. Restart the local server after updating (`.venv/bin/python -m reg_assistant.cli serve`) and rebuild its UI with `cd site && npm run build:pages`.

The conversation controller uses the unadapted instruction model; the legal LoRA remains on the evidence-grounded answer path. Capability replies use runtime metadata, while ambiguous questions produce a clarification. The controller cannot confirm policy changes because historical policy comparison is not implemented. Invalid plans ask for clarification and cannot execute arbitrary tools. The additional interpretation pass and model instance increase latency and memory use.

Model-directed conversation requires the local Python API. Browser-only Pages and the lightweight web API retain their existing retrieval/policy paths. Unit tests cover routing contracts; selected local model smoke checks do not establish general intent accuracy.

App-information questions now use a runtime-facts path: the local model selects models, tools, data or an overview, and the server formats real configuration values. `/api/status` exposes the same snapshot. Model configuration and load state, answer-adapter selection, statutory index coverage, and retailer-tool availability are separate facts. Successful policy-fetch timestamps are recorded for this server session only; a failed later lookup does not erase the previous success. These timestamps do not establish that a policy changed.

Check this first conversational milestone with `.venv/bin/python scripts/check_runtime_queries.py --report tmp/runtime-controller-dev.json`. The nine development cases cover reported app-information failures and non-app controls. This is a scoped development regression check, not held-out controller accuracy or evidence that conversation-state/clarification-loop issues are resolved. The new app-information classification adds an inference pass before the existing routing path.

## Controller sessions and measured selection

The local API now classifies the current message before consulting topic state. Only dependent messages inherit a known task. A short policy-topic fragment can move from retailer support information to official policy lookup; a clear new app or legal question resets the old topic. Model decisions are validated and cannot supply free-form legal or policy answers. Retrieval and citation checks remain responsible for source answers.

Each response includes a `conversation_id`; clients send it on the next request. The server retains only a bounded user topic, retailer and clarification state (128 sessions, one-hour idle expiry, no disk persistence). Previous assistant answers are excluded from controller routing. One unresolved clarification leads to concrete task buttons rather than another clarification loop. New research clears the browser session ID. An expired or restarted session returns HTTP 409 and requires a new conversation.

The selected controller is pinned separately in `configs/controller.json`: Qwen3-4B-Instruct-2507, four-bit MLX. The evidence-answer Qwen2.5 1.5B model, its LoRA, corpus and frozen legal reports are unchanged. Download its files with `.venv/bin/python scripts/download_controller.py`, then restart the server and refresh the built UI.

| Controller replay on the same 22 verification turns | Turn checks passed | Warm median | Peak MLX allocation |
| --- | --- | --- | --- |
| Saved pre-fix controller | 10/22 | 0.75 s | 1.65 GiB |
| New workflow, original 1.5B model | 13/22 | 1.30 s | 1.58 GiB |
| New workflow, selected 4B model | 21/22 | 3.48 s | 3.03 GiB |

These are **routing and state checks, not legal-answer accuracy**. Legal/policy execution was stubbed consistently for controller replay; the pre-fix pipeline is credited for its existing retrieval-query resolver. The verification set was later replayed after an integration correction and should now be treated as a regression set, not newly unseen test data. The selected run had no wrong retailer-tool calls or repeated-clarification violations in this small set. One generic extended-warranty question incorrectly selected an app overview. It remains a documented miss, not a question-specific patch. The first held-out replay failed and became diagnostic data; its results are retained. Verification v2 was frozen before evaluating the revised workflow. Dataset/code hashes, the selection gates, and known misses are in `eval/controller-evaluation-manifest.json` and `reports/controller-selection.json`.

Reproduce the new-workflow comparison in separate processes:

```sh
.venv/bin/python scripts/evaluate_controller.py --cases eval/controller-conversations-verification-v2.jsonl --model configs/controller-baseline.json --output reports/controller-same-architecture-1.5b-verification-v2.json
.venv/bin/python scripts/evaluate_controller.py --cases eval/controller-conversations-verification-v2.jsonl --model configs/controller-candidate.json --output reports/controller-candidate-verification-v2.json
.venv/bin/python scripts/evaluate_controller.py --cases eval/controller-conversations-verification-v2.jsonl --model configs/controller-baseline.json --legacy eval/baselines/controller_before.py --output reports/controller-before-fix-verification-v2.json
.venv/bin/python scripts/select_controller.py --check
```

The saved pre-fix run identifies its archived local source by hash; its versioned replay module is `eval/baselines/controller_before.py`. It is historical evidence, not the current controller. Do not infer broad intent accuracy or legal safety from these small, hand-authored conversation checks. MLX allocation measures the controller process, not the complete serving stack or total Mac memory.

Vector storage and S3 are later phases. A vector backend should preserve retrieval/citation and version-filtering contracts; S3 would hold versioned source and evaluation artifacts, with manifests/checksums linking them to the index. No cloud resources are needed for this conversation fix. Multi-process/cloud serving will also require shared, authenticated session storage rather than this local process's in-memory sessions.

## Next routing-boundary evaluation suite

[Routing-boundary fixtures](eval/routing-boundary/README.md) add 64 synthetic question turns: 32 development and 32 reserved hold-out. They contrast consumer-law requests with app-information questions, and include supported/unsupported retailer boundaries and multi-turn switches. These are newly prepared routing labels, not legal gold answers or a new model score. The controller and existing 22-turn regression set are unchanged. Validate integrity without model inference using `.venv/bin/python scripts/validate_routing_boundary.py`. Reserve the hold-out split until after development tuning.
