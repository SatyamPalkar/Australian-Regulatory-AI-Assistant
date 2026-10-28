# Phase-two conversation and explanation experiment

Explanation structure and qualification-keyword scores are proxies, not factual correctness. Development source review found substantive errors; original concise adapter remains the default. New adapter is experimental. Both test and training examples are synthetic; independent review pending.

Both adapters use the same explanatory prompt, 512-token cap, retrieval and bounded conversation context. This isolates the adapter comparison; the production default remains the original concise profile.

| Adapter | Supported answered | Three-part cited explanation | Qualification keyword coverage | Unsupported declined | Median latency |
| --- | --- | --- | --- | --- | --- |
| [v1-explain](phase2-test-v1-explain.json) | 40.0% | 0.0% | 25.0% | 100.0% | 0.78 s |
| [v2-explain](phase2-test-v2-explain.json) | 60.0% | 60.0% | 35.0% | 100.0% | 0.98 s |

10 supported and six unsupported questions. Contextual follow-ups cited the expected source for one of two supported follow-up cases in each model run. False abstentions and rejected generations are retained in the JSON reports.

The new adapter trained on 64 source-authored examples for 120 steps; step 120 had the lowest saved-checkpoint validation loss. Validation shares source topics and targets with training. Ten training source sections are disjoint from eight test source sections. This corpus and related topics have already been inspected, so this is not an independent legal benchmark.

Training: 145.1 seconds, 2.47 GB peak MLX allocation. This excludes CPU model allocations and other applications.

**Serving decision:** retain `adapters/consumer-law` with concise answers. Development proxies favored the new candidate, but a source spot-check found wrong supplier/consumer roles and misstatements of the title guarantee. See [development review](phase2-development-review.json) and [selection record](phase2-selection.json). More paragraphs do not establish better legal answers.

Default dependent follow-ups return fresh verbatim statutory text, labelled as source wording, because live checks also found qualification errors in the original adapter. The new adapter remains available through an explicit experimental command. Human factual correctness and citation-entailment review CSV fields are blank. The original v1 benchmark files, training data and reports remain unchanged.

See [PHASE2.md](../PHASE2.md) for reproduction, history limits and observed failures.
