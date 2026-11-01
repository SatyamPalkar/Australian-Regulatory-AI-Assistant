# Running and deploying the web application

## Render free demo (Groq + lightweight retrieval)

Use the repository-root `render.yaml` as a Render Blueprint:
[Deploy this repository on Render](https://render.com/deploy?repo=https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant).
It specifies the **Free** compute plan, one Python worker and `/api/health`.
Enter `GROQ_API_KEY` directly in Render's environment settings when prompted.
Never commit it or put it in a GitHub Actions variable. The Python version is
3.13.5, matching the tested local API environment.

If using the dashboard's **New Web Service → Public Git Repository** form:

| Field | Value |
| --- | --- |
| Repository | `https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant` |
| Branch | `main` |
| Root directory | Leave empty: this Git repository already contains the app at its root |
| Runtime | Python 3 |
| Compute plan | **Free — $0/month, 512 MB** |
| Build command | `pip install -r requirements-render.txt && python scripts/prepare_semantic_cpu.py` |
| Start command | `uvicorn reg_assistant.deployment:create_render_app --factory --host 0.0.0.0 --port $PORT --workers 1 --no-access-log` |
| Health check | `/api/health` |
| Environment | `GROQ_API_KEY` as a secret; `PYTHON_VERSION=3.13.5` |

The default allowed browser origin is `https://satyampalkar.github.io`.
`REGULATORY_ALLOWED_ORIGINS` can supply comma-separated HTTPS origins without
paths. The API key must be present in Render's environment before startup.
The free profile uses a pinned 23 MB quantized MiniLM ONNX model for 384-dimensional
embeddings, fused with TF-IDF using reciprocal ranks. Both corpus chunks and
queries use the same encoder, masked mean pooling and normalization. The build
verifies asset hashes and embeds all 93 chunks; requests never download models.
The index is bound to the corpus, chunk order and embedding configuration.
A missing or stale index fails explicitly rather than silently using lexical search.

No MLX, Torch, cross-encoder or LoRA adapter is loaded. This remains a different
retrieval profile from the local hybrid/reranker experiments. Existing structural
citation checks, source quotations, prepared summaries and retailer lookup remain.
Semantic cosine >= 0.50 is a development-tuned relevance gate, not a probability
of factual support. The generator must still assess support and cite its answer.

To roll back explicitly, set `REGULATORY_RETRIEVAL_PROFILE=tfidf` and redeploy.
The default is `semantic_cpu`. Changing tracked `render.yaml` does not update
manually created services: update their dashboard build command as well.

### Connect the public GitHub Pages interface

After Render reports **Live**, check `<Render service URL>/api/health` and
`/api/status`; status must identify `groq` and `semantic_cpu`. Then:

1. In this GitHub repository, open **Settings → Secrets and variables → Actions →
   Variables**. Add the repository variable `REGULATORY_API_BASE` with the exact
   HTTPS Render origin, such as `https://your-service.onrender.com` (no `/api`
   suffix, credentials or query string). This URL is public configuration.
2. Run **Actions → Deploy chatbot to GitHub Pages → Run workflow**. The workflow
   passes the public URL as `VITE_REGULATORY_API_BASE` during the frontend build.
3. Open the project from the portfolio. It should show **Groq AI · Semantic
   RAG**, not Browser retrieval demo. A failed API request remains an error;
   it does not silently become a browser-only answer.

Without that variable, Pages intentionally stays in browser-only mode. Changing
only the portfolio description does not connect the API. The mode panel also
lets an individual visitor explicitly connect a server without a rebuild.
Do not set `GROQ_API_KEY` or a `VITE_*` API-key variable in GitHub or the frontend.

### Public-demo limits

The single worker allows one active model task, buffers at most 16 KiB per ask,
requires JSON and limits requests before calling Groq. Defaults are 8 attempts
per minute globally, 3 per minute per server-observed client address, and 40
attempts per UTC day. Configure these using `REGULATORY_REQUESTS_PER_MINUTE`,
`REGULATORY_CLIENT_REQUESTS_PER_MINUTE` and `REGULATORY_REQUESTS_PER_DAY`.
Quota responses return 429 with `Retry-After` and appropriate CORS headers.

These are in-memory prototype limits, reset by restarts, not authentication or
a guaranteed spending cap. CORS is not authentication either. Multiple visitors
may share an observed proxy address; forwarded headers are not trusted by this
limiter. Keep one worker/instance, retain Groq's own usage controls, and add
durable abuse protection before scaling. Request bodies and IP addresses are
not written to application access logs by the provided start command.

Render's free service sleeps after inactivity; cold starts delay the first
request. Groq quotas also apply. This setup avoids using your Mac as a public
server, once the Render service and frontend connection are both live.

Run the integration checks against the deployed service:

```sh
python scripts/check_groq_app.py --origin https://your-service.onrender.com --pause 25 --output reports/render-lightweight-smoke.json
```

For local testing only, export `GROQ_API_KEY` into the process environment and
run the same factory on loopback. The factory deliberately requires the key in
the environment rather than silently reading a packaged `.env` file.

## Optional Groq-hosted inference

Keep the credential only in the server's `GROQ_API_KEY` environment variable or
the ignored project-root `.env`. `.env.example` contains no working credential.
Run `python -m reg_assistant.cli serve --provider groq` after building the UI and
hybrid index as below. The default without this flag remains local MLX inference.

`configs/groq.json` selects `qwen/qwen3.8-27b` with reasoning disabled and
temperature zero. Both controller and answer generator use this hosted model.
Provider aliases can change; the immutable local MLX revision and custom LoRA
are not reproduced by this profile. Embeddings and reranking still use the
downloaded local models. Model facts/status and the UI identify the provider;
historical experiment results continue to describe the original local models.

Questions, bounded context and retrieved evidence leave the machine for Groq.
The browser receives no API credential. Authentication failures, timeouts,
truncated responses and quota errors fail explicitly; quota errors return HTTP
429 and do not automatically retry, switch models or run local inference.
Citation checks verify reference structure, not factual entailment.

Evaluate routing independently, using synthetic fixtures and paced requests:

```sh
python scripts/evaluate_controller.py --provider groq --cases eval/routing-boundary/dev.jsonl --output reports/groq-routing-boundary-dev.json
python scripts/evaluate_controller.py --provider groq --cases eval/controller-conversations-verification-v2.jsonl --output reports/groq-controller-regression.json
```

The reserved routing holdout is not used for this integration. Report latency
includes deliberate request pacing and cannot be compared directly to local
inference latency. Hosted inference does not host the Python API or deploy the
portfolio. Keep the server bound to loopback until public hosting is configured.

With a Groq-backed server running on port 8001, test the complete API path and
check desktop/mobile provider labels separately:

```sh
python scripts/check_groq_app.py --origin http://127.0.0.1:8001 --pause 35
cd site
QA_UI_ONLY=1 QA_BASE_URL=http://127.0.0.1:8001/Australian-Regulatory-AI-Assistant/ node scripts/browser-qa.mjs
```

The live smoke test makes hosted requests and one official retailer-policy
lookup. It covers citations, source presence, simplification, app facts,
unsupported questions and topic changes; it does not certify legal accuracy.

## Local model-backed application

The Python API serves the built React application and runs real hybrid retrieval,
reranking and MLX generation with the trained LoRA adapter. Follow the Mac setup in
`README.md` (pinned dependencies, model downloads, hybrid index and training), then:

```sh
cd site
npm run build:pages
cd ..
python -m reg_assistant.cli serve
```

Open `http://127.0.0.1:8000/Australian-Regulatory-AI-Assistant/`. Use `serve
--base-model` for the unadapted model. The API overrides `runtime-config.js` so the
same UI selects the same-origin local API. It binds to loopback, accepts at most
2,000 characters per question, and serialises model requests. API errors do not
silently fall back to lexical answers. No API key is embedded in frontend code.

Download the independently pinned controller with `.venv/bin/python scripts/download_controller.py` before starting the updated server.

Requests should carry the previous response’s `conversation_id` to retain bounded topic state. New research omits that ID. Sessions expire after one idle hour; HTTP 409 means restart the conversation. The store is in-memory and single-process (128 sessions), with no disk chat persistence.

Requests may include up to three prior `{question, answer}` turns; the server bounds their combined text to 6,000 characters. Dependent default follow-ups return fresh source wording. Use `--answer-style explain --adapter adapters/explanatory-v2-selected` only for the experimental explanation profile described in `PHASE2.md`.

The API exposes `/api/health`, `/api/status`, `/api/ask`, `/api/evaluation` (the saved
lexical development baseline) and `/api/experiments` (the four frozen model runs).
The UI shows generated prose, clickable references, underlying statutory evidence,
timing/token/memory details, and a separate model-comparison table. Its model request
timeout is three minutes to allow first-load latency.

Automated model-backed browser verification, after the API is running:

```sh
cd site
QA_RAG_MODE=1 QA_BASE_URL=http://127.0.0.1:8000/Australian-Regulatory-AI-Assistant/ node scripts/browser-qa.mjs
```

The Pages mode control can connect an explicitly entered API origin. Allowed CORS
origins are listed in `reg_assistant/api.py`. Browser private-network policies may
prevent an HTTPS Pages website from contacting a localhost API; the same-origin
local app is the supported path. This local server is not a public hosting service.
Public model hosting requires a separate authenticated inference deployment;
GitHub Pages does not run Python, MLX or model weights.

## GitHub Pages

Public application: [Australian Regulatory AI Assistant](https://satyampalkar.github.io/Australian-Regulatory-AI-Assistant/).

GitHub Pages serves the static build under `/Australian-Regulatory-AI-Assistant/`.
The same React UI and TF-IDF engine run entirely in the browser, using the bundled
37 statutory sections, 93 retrieval passages and saved evaluation report. Questions
stay in browser memory; this variant does not call the Worker API or the private
Sites deployment. Copying, source details, section search and research export work
without a separate server. The mode control can explicitly connect an API; that
sends questions to the entered server instead. Actual MLX inference runs in the
local Mac API described above. The Evaluation page includes the saved model
comparison even when no model server is connected.

### Build and preview

From the repository root:

```sh
python3 scripts/export_site_data.py
python3 scripts/export_experiments.py
cd site
npm run install:ci
npm run typecheck
npm test
npm run build:pages
npm run preview:pages
```

Open `http://127.0.0.1:4174/Australian-Regulatory-AI-Assistant/`.
The static output is ignored `site/pages-dist/`. The alternate Vite entry is in
`site/github-pages/`, and `vite.pages.config.ts` applies the project URL prefix to
scripts, styles, the favicon and the home link. The optional `PAGES_BASE_PATH`
build variable overrides that prefix for another deployment path.

Browser verification of the static build:

```sh
cd site
QA_STATIC_MODE=1 QA_BASE_URL=http://127.0.0.1:4174/Australian-Regulatory-AI-Assistant/ node scripts/browser-qa.mjs
```

This checks citations, source metadata, section search, evaluation, reset and mobile
layout. It also rejects backend/private-Site requests and checks the home link's
project prefix. Set `CHROME_PATH` if Chrome is installed elsewhere.

### Automatic deployment

`.github/workflows/pages.yml` runs on pushes to `main` and manual workflow dispatch.
It verifies Python tests and deterministic data exports, installs locked dependencies,
checks types and retrieval parity, builds the static app, uploads the Pages artifact
and deploys it to the `github-pages` environment. The deploy job uses GitHub's Pages
and OIDC permissions; no personal token is stored in the workflow or application.

The repository's **Settings → Pages → Source** is configured as **GitHub Actions**.
For administrative status/configuration, `scripts/github_pages.py status` and
`enable` use an existing Git credential or `GH_TOKEN`/`GITHUB_TOKEN` in process
memory. The helper never writes or prints credentials. `runs` and `jobs --run-id ID`
show deployment progress. Pushes to GitHub publish Pages automatically; the private
Sites deployment has its own separate publication workflow below.

## Optional private Sites / Worker deployment

Private Worker application: [Australian Regulatory AI Assistant](https://australian-regulatory-ai-assistant.snowybead1.chatgpt.site).
It is deployed with owner-private access through Sites.

The `site/` application provides the full browser-to-server retrieval flow. The
React interface calls same-origin API routes on a Cloudflare Worker. The Worker
searches an exported copy of the Python TF-IDF index and returns cited passages.
No third-party LLM API key is needed.

The hosted corpus contains 37 real Australian Consumer Law sections from the pinned
Hugging Face `cchew/lex-au` dataset, indexed as 93 passages. Its source compilation
is 27 August 2026; a newer official compilation was listed when checked. See
`data/ATTRIBUTION.md` for provenance, currency and CC BY 4.0 attribution. It is
an extractive research demo; semantic embeddings, MLX generation and fine-tuning
are not running on the hosted Worker. MLX requires Apple Silicon and remains in
the Python CLI workflow described in `README.md`.

## Local development

Requirements: Node.js 24 and Python 3.9+. From the repository root:

```sh
python3 scripts/export_site_data.py
cd site
npm run install:ci
npm run dev
```

Open `http://localhost:5173`. The UI includes a question composer, clickable example
questions, cited evidence, source details, statutory source and dataset links, an evaluation
view, copying, and JSON research exports. Questions stay in browser memory and
reset on refresh; the application does not store a conversation database.

To test the production build locally:

```sh
cd site
npm run typecheck
npm test
npm run build
npm start
```

Open `http://127.0.0.1:8787`. `npm start` uses a local Worker runtime with the
production build; it is a local verification server, not a public hosting command.

## Backend API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` | Health, active corpus fingerprint, source metadata and limitations |
| `POST /api/ask` | Search the corpus; accepts JSON `{"question":"What guarantee applies to services supplied with due care and skill?"}` |
| `GET /api/evaluation` | Saved development report shown in the evaluation view |

Question requests are limited to 2,000 characters. Invalid JSON, unsupported content
types, oversized bodies and cross-origin browser requests are rejected. Responses
include provenance, evidence text, ranked retrieval results, an abstention flag and
server retrieval latency. This latency does not include network or model inference.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 scripts/export_site_data.py
cd site
npm test
npm run typecheck
npm run build
```

The Python suite covers retrieval and ingestion. The web suite tests API contracts
and exact output parity against Python on the twelve development questions. The
GitHub Actions workflow repeats export consistency, tests, type checking and the
production build for pushes and pull requests. It does not automatically deploy
to Sites; publication uses the Sites source/version workflow.

Optional browser QA uses an installed Chrome and a running production server:

```sh
cd site
node scripts/browser-qa.mjs
```

Set `CHROME_PATH` on other systems and `QA_BASE_URL` if the local server uses another
port. The script checks supported and unsupported questions, citations, source
details, library/evaluation navigation and mobile overflow. Screenshots are saved
under ignored `site/outputs/`.

## Sites publication

The Site's stable identity is in `site/.openai/hosting.json`. Keep that ID when
updating this deployment. New Sites are owner-private by default. The GitHub
repository and the Sites source repository are separate: pushing to GitHub alone
does not publish a new Site version.

Publish using the Sites skill's supported workflow:

1. Obtain a short-lived source write credential for the existing project ID.
2. Use a dedicated publication checkout containing the `site/` source and manifest.
3. Run the checks/build, then use the source helper to push the exact source and
   package its matching `dist/` output. Keep credentials in session memory and pass
   them to the helper over stdin.
4. Save and deploy the matching commit/archive using the private deployment tool.
5. Wait for a successful deployment result and record its URL/version.

No source tokens or runtime secrets belong in GitHub, the hosting manifest or an
archive. This application has no database, storage bindings or paid model API keys.

## Updating the corpus

Review the pinned manifest `data/huggingface_sources.json` and reproduce the import
with `python3 scripts/import_huggingface.py`, then rerun the Python development evaluation
before exporting the web corpus and fixtures:

```sh
python3 -m reg_assistant.cli index
python3 -m reg_assistant.cli evaluate
python3 scripts/export_site_data.py
```

Review all new evidence, evaluation failures and `site/lib/` changes before
publishing. Keep an independent held-out set for the later fine-tuning comparison.
The UI shows saved development results and does not claim a fresh evaluation run.
