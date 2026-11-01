# Public Render deployment — 1 November 2026

The free Render service is live at
[australian-regulatory-api.onrender.com](https://australian-regulatory-api.onrender.com).
Status identifies Groq inference and `semantic_cpu` retrieval. The embedding
model was verified enabled and loaded after a real statutory request. There are
37 statutory sections in 93 chunks, no cross-encoder reranker and no LoRA adapter.
The credential remains a server-side Render environment value.

The public [GitHub Pages interface](https://satyampalkar.github.io/Australian-Regulatory-AI-Assistant/)
shows **Groq AI · Semantic RAG** and labels CPU semantic embeddings + TF-IDF.
The portfolio description matches this profile. GitHub CI and Pages deployment
succeeded for implementation commit `c2499a1`. The automated suite has 126 Python
and 39 web tests, all passing.

[Seven deployed semantic API checks](render-semantic-deployed-smoke.json) passed:
model facts, cited title guarantee, typo-heavy plain-language follow-up, model
facts after a topic switch, unsupported current fee, official JB Hi-Fi policy
lookup, and a switch back to section 54. Every response trace identified
`semantic_cpu`. These checks establish routes, expected source presence and
citation structure, not independent legal correctness.

The [CPU retrieval development report](semantic-cpu.md) describes the 20/20
existing development checks, local memory measurements and additional paraphrase
misses. Local process memory is not a measurement of Render container memory.
The deployed service handled all seven checks without an observed memory failure.

The original local hybrid/MLX/LoRA experiments remain separate. Their historical
metrics do not describe this cloud profile. The initial TF-IDF-only rollout is
preserved in [its earlier smoke report](render-deployed-smoke.json). Render can
sleep when idle; Groq and demo request budgets apply. The Mac is not the public
server.
