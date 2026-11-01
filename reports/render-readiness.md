# Render free-profile readiness — 1 November 2026

The user selected a free demo with explicitly lighter retrieval. The new
`render.yaml` and `requirements-render.txt` deploy the Groq controller/generator
with TF-IDF evidence retrieval. Torch, embeddings, cross-encoder reranking,
MLX and LoRA adapters are not loaded by this deployment profile. The original
local hybrid/LoRA workflow remains available.

- 118 Python tests passed, including origin checks, streamed request-size bounds,
  per-client/global/day budgets, UTC resets, explicit section filters, unsupported
  questions, citation rejection and the plain-language follow-up regression.
- 39 web tests, TypeScript checks and both builds passed.
- [Seven live checks](render-lightweight-smoke.json) passed against the Render
  profile running locally with real Groq calls and an official policy fetch.
  These are integration/structure checks, not independent legal-accuracy scores.
- A subprocess test blocks imports of Torch, MLX, Transformers and Sentence
  Transformers while executing the lightweight retrieval path.
- The frontend build includes an explicitly configured public HTTPS backend URL,
  rejects malformed backend configuration without printing its value, and labels
  the new profile as **Groq AI · Lightweight RAG**.
- The Blueprint selects the Free plan, a secret placeholder and a health check.
  Its structure and safety fields were checked locally, not through Render's
  authenticated Blueprint validator.

The initial live replay exposed wording-only follow-ups diluting the lexical
topic. Retrieval now retains the topic for simplification requests, and the
rerun passed. The initial diagnostic report is retained outside Git.

This report does not certify Linux resource usage, successful Render deployment,
or a connected public frontend. Those require a live Render service and the
GitHub repository variable `REGULATORY_API_BASE` set to its actual HTTPS origin.
The provided limits are single-process prototype controls, not authentication
or a guaranteed spending cap; see [deployment instructions](../DEPLOYMENT.md).
