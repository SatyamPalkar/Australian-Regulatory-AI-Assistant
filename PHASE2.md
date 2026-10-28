# Conversation context and explanatory LoRA experiment

The local API now accepts bounded conversation context. A second LoRA adapter was
trained and evaluated for richer explanations. The experiment improved response
structure, but source review found substantive errors. The original adapter stays
the default for standalone questions; dependent follow-ups return fresh source
wording. The explanatory adapter is opt-in and is not a legal-accuracy upgrade.

## Conversation behaviour

The browser sends up to three completed question/answer turns to the local API.
Each prior question is limited to 2,000 characters and each answer to 4,000. The
server keeps recent complete turns within a 6,000-character total budget. It does
not store sessions or conversation files. Resetting the chat or refreshing clears
the frontend history. Research exports remain explicit downloads.

The resolver uses prior **user questions** to add topic words to dependent
follow-ups such as "What are the exceptions?" or "Does that apply to hire or
lease?". Earlier assistant claims are not retrieval evidence. Explicit new section
requests and standalone topic changes retain their own retrieval. This is a
conservative rule-based resolver; arbitrary ambiguous references are not solved.

Every turn retrieves fresh evidence with fresh reference numbers. In the default
profile, a dependent follow-up returns the strongest admitted provision verbatim,
labelled **Source wording**, with a citation and scope note. It skips generation
instead of risking an invented exception. The complete short provision preserves
its qualifications; long provisions can still be partial. Standalone questions
use the original concise adapter and ignore irrelevant prior turns in generation.

The experimental explanatory profile supplies bounded prior dialogue as explicitly
untrusted context, separate from newly retrieved evidence. Prior answers and their
reference numbers are never authoritative sources. This prompt instruction is not
a guarantee against prompt injection or semantic mistakes.

GitHub Pages' browser-only retrieval demo remains stateless. Conversation-aware
behaviour requires the local API.

## Training and split

`data/training-phase2/` contains 64 synthetic examples: 30 ordinary explanations,
20 follow-ups, four two-source examples with swapped citation order, and ten
unsupported/instruction-attack examples. Targets use **Rule / Meaning / Limits**
paragraphs with citations, based on ten statutory sections. They were source-checked
during authorship; independent legal and entailment review is pending.

Ten validation examples share source topics and answer targets with training, so
validation loss is not an independent generalisation measure. The 16-question test
has ten supported questions (including two follow-ups) and six unsupported
questions. Eight supported test sections are disjoint from training. The corpus
and related topics were already inspected; no independent legal benchmark claim
is made. Training also excludes the original v1 test-source sections.

`eval/phase2-manifest.json` freezes all new input hashes and the corpus before
training. Original v1 data, its split manifest and reports remain unchanged.

Training used the same pinned four-bit Qwen 1.5B model, rank four over four layers,
batch one, seed 43, learning rate 0.00005 and 120 steps. Maximum sequence length was
1,536; actual maxima were 1,011 training tokens and 944 validation tokens, so no
examples were truncated. Prompt tokens were masked. Step 120 had the lowest
validation loss among saved checkpoints and was copied into a separate selected
adapter directory. Final/checkpoint weights are preserved locally and excluded
from Git.

The run took 145.1 seconds and 2.47 GB peak MLX allocation on the M3 Pro. This
allocator measurement excludes CPU models and other applications. Logs, losses,
hashes and hardware are in `reports/lora-phase2.json` and `.txt`.

## Results and serving decision

[Full comparison](reports/phase2-comparison.md). Both adapters used the same new
explanatory prompt, 512-token output limit, retrieval, evidence gate and history
settings. On the new test, accepted cited responses increased from 4/10 to 6/10
supported questions; three-part explanations increased from 0/10 to 6/10. Both
declined 6/6 unsupported questions. These counts include retrieval and structural
output rejection, and do not establish factual correctness.

The qualification-keyword proxy increased from 25% to 35%. A word appearing in an
answer can still be used incorrectly. On development data, the new adapter
misstated the title guarantee and confused supplier/consumer roles, despite passing
format and keyword checks. A live original-adapter follow-up also misstated a
qualification after retrieving the correct section. These findings motivated the
source-quoted default follow-ups and prevented promotion of the explanatory model.

`reports/phase2-selection.json` records the automated development-proxy candidate
and the separate serving decision. The source spot-check is retained in
`reports/phase2-development-review.json`; it is an implementation review, not an
independent legal evaluation. Human factual-correctness/entailment fields in the
CSV files remain ungraded. Test results were not used to choose or tune the
adapter. Further tuning requires development data and a fresh frozen test for new
generalisation claims.

## Run locally

Use the README's Mac environment and pinned models. For a checkout without the
new adapter, training recreates it:

```sh
python scripts/train_lora.py --phase2
python -m reg_assistant.cli serve
```

Default app: `http://127.0.0.1:8000/Australian-Regulatory-AI-Assistant/`.

To explicitly compare the experimental model on another port:

```sh
python -m reg_assistant.cli serve --adapter adapters/explanatory-v2-selected --answer-style explain --port 8001
```

The interface labels explanatory mode experimental. To reproduce evaluations:

```sh
python scripts/evaluate_phase2.py --suite dev
python scripts/evaluate_phase2.py --suite test
python scripts/export_phase2.py
```

The frozen preparation and selection records are already committed. Preparation
refuses to overwrite frozen data; training refuses to overwrite existing adapters.
Re-running evaluations produces a new measurement of an already-observed test,
not a new independent result. Preserve original reports when conducting new work.
