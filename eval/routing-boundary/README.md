# Routing-boundary evaluation data

This is the **data-preparation step**, not a routing change or a new accuracy result.
The current controller, its prompts, models, source corpus, and original 22-turn
regression set are unchanged. The unchanged controller has now been run on the
development split only: **30/32 turn checks passed**. The reserved hold-out split
has not been sent to the controller. See `reports/routing-boundary-baseline-dev.json`
for the raw development results; this is a routing baseline, not legal-answer accuracy.

| Split | Conversations | Turns | Consumer law | App information | Supported retailer policy | Unsupported retailer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 28 | 32 | 14 | 12 | 3 | 3 |
| Reserved hold-out | 28 | 32 | 12 | 14 | 3 | 3 |

The suite has eight legal/app contrast pairs and four three-turn conversations.
Standalone questions cover warranty concepts and expiry, refund remedies,
consumer guarantees, service problems, app model/configuration questions, source
coverage, and tool availability. Informal wording and spelling mistakes are
included. Multi-turn cases cover topic carry-over and switches between app
information, legal research and retailer policy.

A contrast pair deliberately shares vocabulary while changing the requested task.
For example, the development split contrasts a different delivered product
**model** with the AI **model** answering warranty questions. It also contrasts a
refund remedy with whether refund guidance is indexed by this app.

## Label contract

- `consumer_law`: `law` intent and `statutory` action. Retrieve evidence, then assess
  coverage. This label **does not mean the current corpus can answer the question**.
- `app_information`: model/tool/data/overview intent and `chat` action. Facts must
  come from runtime configuration, not legal retrieval or model memory.
- `retailer_policy`: the available official JB Hi-Fi tool, with cited policy text
  or an explicit lookup failure. Do not substitute statutory text for store terms.
- `unsupported_retailer`: explain the supported-tool limit; do not fetch JB Hi-Fi
  terms as a substitute for another retailer.

`answer_expectation` prepares the evidence/coverage checks for the later end-to-end
step. There are no gold legal answers or claims about legal entitlements here.

## Integrity and split discipline

Questions are project-authored synthetic scenarios; their intent labels have not
been independently reviewed. Declared scenario families
stay within one split, including spelling variants and contrast-pair members.
Broad legal topics intentionally overlap across splits. Family labels and exact
text checks cannot establish complete semantic independence or absence from model
pretraining; this is not an independently authored blind benchmark.

`manifest.json` pins both files and the existing 22-turn regression file by SHA-256.
Validation rejects duplicate IDs/questions, split-crossing families, malformed
intent/action labels, invalid contrast pairs and exact reuse of existing regression
or controller-prompt questions. It does not load an LLM or assess routing accuracy.

```sh
.venv/bin/python scripts/validate_routing_boundary.py
```

Next, measure the **development** baseline before changing routing:

```sh
.venv/bin/python scripts/evaluate_controller.py \
  --cases eval/routing-boundary/dev.jsonl \
  --model configs/controller.json \
  --output reports/routing-boundary-baseline-dev.json
```

Use development failures for prompt/workflow changes. Keep `holdout.jsonl` reserved
for the later evaluation step: do not put its questions into prompts or use its
results to tune the same reported benchmark. If it is consumed for diagnosis,
record that change of status and reserve a fresh set. Retain the old 22-turn file
as regression coverage; its earlier 21/22 result is not a score for this suite.

Controller replay measures routing/state only and stubs source-answer execution.
Later end-to-end checks must separately test relevant retrieval, citation support,
coverage limitations, current-policy lookup failures and runtime-fact accuracy.
