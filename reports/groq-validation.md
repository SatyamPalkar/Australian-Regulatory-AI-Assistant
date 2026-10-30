# Groq integration validation — 31 October 2026

The optional Groq profile uses `qwen/qwen3.8-27b` for controller decisions and
evidence answers, with reasoning disabled and temperature zero. The local MLX
profile remains available; its LoRA adapter is not used by Groq.

| Check | Local controller reference | Groq result |
| --- | --- | --- |
| Development routing boundary | 30/32 | 32/32 |
| Existing conversation regression | 21/22 | 22/22 |

Both Groq replays recorded zero invalid plans, wrong policy-tool calls or
repeated clarification violations. These are small project-authored synthetic
fixtures, not independent measures of general accuracy. The reserved routing
holdout was not queried or used for tuning. The prompts and state rules were not
changed to obtain these results.

- [Development replay](groq-routing-boundary-dev.json), compared with
  [the unchanged local controller](routing-boundary-baseline-dev.json).
- [22-turn Groq regression](groq-controller-regression.json), compared with
  [the existing selected local controller](controller-candidate-verification-v2.json).
- [Seven full-path API checks](groq-app-smoke.json): 7/7 passed. Covers runtime
  model facts, cited title-guarantee answers, the reported plain-language
  follow-up, topic changes, an unsupported current-fee question, live official
  JB Hi-Fi policy retrieval and acceptable quality after a retailer topic.
- [Reported electronics-warranty question](groq-warranty-smoke.json): passed
  routing, section 59 retrieval, generated-answer, citation-structure and
  provider/adapter checks on the final server at port 8000.

Automated validation passed: **106 Python tests and 39 web tests**, TypeScript
checking, GitHub Pages and application builds, the routing-fixture validator,
existing controller-selection provenance gates and unchanged frozen exports.
The Pages exporter was checked with Python 3.9; Python 3.13's floating-point
summation changes produce insignificant numeric differences in that old export.

Headless Chrome checks passed for Groq desktop/mobile labels and data-flow
notice, and for the complete static Pages flow: cited passages, source dialog,
library search, evaluation, reset, unsupported questions and mobile layout.

The server-only credential file is ignored by Git and has mode `0600`.
Credential scans passed for versionable files and frontend assets. Mocked tests
cover authentication, timeouts, rate limits, redirects, malformed/truncated
answers, credential echoes, invalid routes and invalid citations. API failures
do not silently switch providers or use local language models.

## Reproduce

```sh
python scripts/evaluate_controller.py --provider groq --request-interval 8 --cases eval/routing-boundary/dev.jsonl --output reports/groq-routing-boundary-dev.json
python scripts/evaluate_controller.py --provider groq --request-interval 6 --cases eval/controller-conversations-verification-v2.jsonl --output reports/groq-controller-regression.json
python -m reg_assistant.cli serve --provider groq --port 8001
# In a separate terminal:
python scripts/check_groq_app.py --origin http://127.0.0.1:8001 --pause 35
```

Routing replay latency includes deliberate pacing; it is not a direct
comparison of model speed. The provider-managed model alias is not an immutable
weight revision. Citation structure and expected-source presence do not prove
factual support or legal correctness. Existing model-comparison tables still
describe the earlier local experiments, not Groq results.

Groq receives questions, bounded conversation context and retrieved evidence.
Embeddings, reranking and the Python API still run locally. This integration is
not a public backend deployment. The original static Pages demo continues to
run browser retrieval without model inference.
