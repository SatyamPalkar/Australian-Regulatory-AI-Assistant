# Public Render deployment — 1 November 2026

The free Render service is live at
[australian-regulatory-api.onrender.com](https://australian-regulatory-api.onrender.com).
Its health endpoint returned `ok`; status identifies Groq inference, TF-IDF
retrieval, 37 statutory sections and no LoRA adapter. The Groq credential is a
Render server-side environment value, not a GitHub/frontend secret or variable.

The public GitHub Actions repository variable `REGULATORY_API_BASE` contains
only the HTTPS service origin. The subsequent Pages workflow
[completed successfully](https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant/actions/runs/41282718294).
The public interface now shows **Groq AI · Lightweight RAG**. A browser test of
the previously reported `is groq added` question returned model configuration
through the Groq conversation route instead of statutory abstention.

[Seven deployed API integration checks](render-deployed-smoke.json) passed,
including a cited statutory answer, plain-language follow-up, runtime facts,
unsupported current-fee question, official JB Hi-Fi policy lookup and a switch
back to consumer law. These checks assess routes, source presence and reference
structure; they do not independently establish legal correctness.

This is the user-selected free profile. Embeddings and cross-encoder reranking
are disabled. The original local hybrid/MLX/LoRA experiments remain available
and their historical metrics do not describe this cloud retrieval profile.
Render can sleep on inactivity and Groq/demo request budgets apply. The Mac is
not needed to serve visitors.
