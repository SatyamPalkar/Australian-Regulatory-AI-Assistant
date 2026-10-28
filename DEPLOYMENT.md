# Running and deploying the web application

Live demo: [Australian Regulatory AI Assistant](https://australian-regulatory-ai-assistant.snowybead1.chatgpt.site).
It is deployed with owner-private access through Sites.

The `site/` application provides the full browser-to-server retrieval flow. The
React interface calls same-origin API routes on a Cloudflare Worker. The Worker
searches an exported copy of the Python TF-IDF index and returns cited passages.
No third-party LLM API key is needed.

The hosted corpus contains three project-authored ACCC guidance summaries. It is
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
questions, cited evidence, source details, original guidance links, an evaluation
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
| `POST /api/ask` | Search the corpus; accepts JSON `{"question":"Are extended warranties optional?"}` |
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
and exact output parity against Python on the nine development questions. The
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

Update and review `data/demo.jsonl`, then rerun the Python development evaluation
before exporting the web corpus and fixtures:

```sh
python3 -m reg_assistant.cli index
python3 -m reg_assistant.cli evaluate
python3 scripts/export_site_data.py
```

Review all new evidence, evaluation failures and `site/lib/` changes before
publishing. Keep an independent held-out set for the later fine-tuning comparison.
The UI shows saved development results and does not claim a fresh evaluation run.
