# Experiment protocol and results

This experiment asks whether a small LoRA adapter improves evidence-use behaviour
on a local consumer-law RAG system. It does not establish legal correctness.

## Inputs and split

- Corpus: 37 selected ACL sections, 93 retrieval chunks, pinned in
  `data/huggingface_sources.json` with attribution in `data/ATTRIBUTION.md`.
- Models and immutable revisions: `configs/models.json`. Downloads use local
  safetensors, with remote code disabled.
- Training: 28 synthetic examples (20 supported, eight unsupported/instruction
  attacks); validation: five examples. Supported training targets use one complete
  section and one citation. This limits multi-source citation generalisation.
- Test: `eval/benchmark-v1.jsonl`, 24 supported questions and 12 unsupported
  questions. Supported test sections do not occur in training/validation evidence.
  Train and validation share source topics. Related legal topics cross splits, so
  section separation is not topic independence. Pretraining contamination was not
  assessed.
- Origin: examples authored from the snapshot during implementation; no external
  legal expert or independent sampling. They are synthetic research examples.
- Freeze record: `eval/split-manifest.json` hashes test, training, validation and
  corpus. Training targets received a pre-training correction documented there;
  the frozen test was unchanged. Code/tests reject split-file drift.

## Fixed experiment

The lexical baseline uses the existing TF-IDF engine and its coverage gate. Hybrid
retrieval fuses lexical and cosine ranks with RRF constant 60, reranks 12 candidate
chunks, and retains up to three with sigmoid reranker score at least 0.5. Explicit
section references act as user filters. Duplicate evidence sections are collapsed;
sections of at most 600 words are provided in full, while longer ones remain
partial. Retrieval scores express relevance, not answerability.

Both model runs use identical retrieval, evidence assembly, system prompt, greedy
decoding and a 256-token output cap. Every nonempty answer paragraph must end in
valid supplied reference numbers. Rejected raw text is retained in the offline
report but never displayed as the answer. This is a syntax gate, not an entailment
model. A high abstention rate can hide poor usefulness, so supported response rate
is reported separately.

The adapter was trained for a fixed 60 iterations, batch size one, maximum sequence
length 1,024, four adapted layers, rank four, scale eight, seed 42 and learning rate
0.0001. Prompt tokens are masked from the loss. All examples fit: maximum training
length 725 tokens and validation length 706. The smoke run used ten iterations and
maximum length 768. Actual logs are saved as `reports/lora-*.txt`.

The final 60-step adapter was selected for the local app using the development
comparison before the frozen test was evaluated. On development data it produced
accepted cited answers for eight of nine supported questions versus one of nine
for the base model. This is a fixed-step pilot, not a checkpoint search. Validation
loss was lower at step 30 than step 60; lower loss is not evidence of better legal
answers. No test-driven tuning was performed after the comparison.

## Measured results

See [the four-way comparison](reports/comparison.md). Full `reports/test-*.json`
files include every answer, evidence text, retrieval scores, rejected generations,
timings, model identities, split hashes and the adapter checksum.

On the frozen set, hybrid retrieval found an expected section in the top three for
23/24 supported questions, versus 22/24 for TF-IDF. Base RAG produced an accepted
cited answer for 17/24 supported questions; LoRA RAG did so for 20/24. Both model
pipelines declined 12/12 unsupported questions. These are small-sample observations,
not calibrated accuracy estimates. Several unsupported declines came from the
retrieval gate, so they do not isolate model behaviour.

Median end-to-end latency was 0.94 seconds for base RAG and 0.97 seconds for LoRA
RAG on this M3 Pro. Peak MLX allocation was 1.77 GB and 1.94 GB respectively. The
60-step training process took 49.6 seconds and reached 2.32 GB peak MLX allocation.
MLX allocation, process RSS and total unified-memory use are different measures;
these figures exclude other applications and CPU model allocations. The first
request of each pipeline is marked cold and includes loading. This is one run on
one machine, not a throughput/service-level benchmark.

## Failure analysis

- The reranker threshold rejected three supported questions: matching both sample
  and description, guarantees for replacement goods, and manufacturer reduction
  in value. An expected source appearing in the ranked list does not ensure it is
  admitted to the evidence pack.
- LoRA also failed the limited-title exception question: its generation did not
  pass the reference gate. Base and adapted models each have distinct citation
  failures; inspect `raw_generation` before deciding how to fix the prompt/data.
- The small model can still omit exceptions or make an unsupported inference
  despite valid citations. No factual correctness or entailment score is claimed.
- A post-comparison CLI spot check asking "What guarantee applies to services
  supplied with due care and skill?" produced a fitness-for-purpose condition but
  cited section 60 (due care and skill). This is an observed attribution/content
  failure that passed the syntax gate. It is not counted as a new frozen test
  result and was not used to tune the published experiment.
- The statute snapshot predates a newer compilation. Real-world legal accuracy
  cannot be inferred from correct use of an old, selected snapshot.
- Initial CPU float32 reranker inference produced non-finite scores. The validated
  stack uses eager float64 CPU inference and explicitly rejects non-finite values.
  Invalid early development outputs were replaced by the corrected development
  run; no frozen test was run under the invalid scoring implementation.

## Reproduce

Use the README's tested Mac dependency snapshot and model download/index commands.
For a fresh checkout without adapters:

```sh
python scripts/train_lora.py --smoke
python scripts/train_lora.py
python scripts/run_experiment.py --suite dev --modes hybrid base-rag adapter-rag
python scripts/run_experiment.py --suite test --modes tfidf hybrid base-rag adapter-rag
python scripts/export_experiments.py
```

The preparation script is retained for provenance and refuses to overwrite the
frozen benchmark. Use committed splits. Training refuses to overwrite existing
adapters. Model weights and adapter binaries are ignored by Git; reproduction
recreates them locally. Do not put them into a Pages deployment.

## Everyday warranty wording regression

An observed user question, "what are the warranties on electronics products",
initially ranked section 59 first but below the 0.5 relevance gate, leaving no
evidence for generation. Search now maps everyday warranty terminology to express
warranties and common product nouns to goods, preserving brands, dates, amounts,
fees and other qualifications. The threshold remains 0.5. For rewritten queries,
evidence more than three reranker logit units below the strongest hit is omitted
to reduce mixing of unrelated statutory provisions. Generation receives the
original question plus the search interpretation, and the UI labels the answer
as a general statutory overview without brand-specific warranty terms.

`eval/product-warranty-dev.jsonl` and `reports/warranty-query-regression.json`
record three general-warranty cases and five unsupported cases. The real-model
check requires a cited warranty-compliance answer for supported questions and
abstention for brand-specific periods, fees and visa questions. These observed
development regressions are not a new independent test or factual-accuracy score.
Run `python scripts/check_warranty_queries.py` to repeat them. Existing frozen
benchmark files and reports are unchanged; a unit check verifies that every frozen
question keeps identical search wording and follows the original prompt path.

## Independent review still required

Each run has a `reports/*-review.csv` with blank factual-correctness and
citation-entailment fields. A reviewer should inspect all generated claims against
the full cited provisions, including exceptions and snapshot dates. Mark factual
correctness 1 only when every substantive claim is supported and the response
answers the question; mark citation entailment 1 only when every claim's cited
source supports it. Unsupported questions must neither invent an answer nor imply
a case outcome. Record partial answers and scope mistakes in notes. Prefer two
independent reviewers and resolve disagreements. Existing automated source/keyword
checks must never fill these columns.

This test is now observed. Further iterations must use development data; create a
new independently authored, frozen test before making new generalisation claims.
