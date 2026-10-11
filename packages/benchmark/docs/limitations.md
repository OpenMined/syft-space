# Known limitations of the methodology

What this measurement cannot do, or does only conditionally.

## Judging

* **The judge is a model.** A panel measures agreement between judges, but high
  agreement means the judges are alike, not that they are right. The judge's
  name is part of every number: it is in the report and the published card.
* **A console judge grades only the `direct` block.** `denial_loop` and
  `monte_carlo` verdicts are issued during the run; the console judge did not
  see the rounds.
* **A human verdict cannot be rechecked like a machine one.** The audit record
  marks it.
* **Text metrics know nothing of correctness.** BLEU, ROUGE and BERTScore
  measure resemblance to the gold answer; they are off by default, enter no
  share, and compare only within one report.

## The set

* **Gold-answer screening is lexical**: deterministic and cheap, but a
  legitimate paraphrase may fall short of the coverage threshold.
* **The control set's labelling is relative and costs a call per candidate.**
  "No answer" holds only for a specific endpoint. The gate errs towards
  strictness: it drops fit negatives rather than accuse a model of invention.
* **Document-level generators are heavy for small models.** On a local 4B
  model, `multihop_synthesis` and `tiered_explanation` often invent; screening
  catches it, after the time is spent.
* **Cohorts built by one generator model prove reproducibility, not
  correctness.** An independent check needs a second generator model.
* **A frozen slice pins the questions, not the corpus.** Reindexing the Space
  changes the answers. A frozen slice and a rolling set contradict each other.
* **A rolling set makes days non-comparable question by question.** Compare
  behaviour across days (abstention share, the price of context), not accuracy
  on a particular set.
* **The freshness window relies on the node's date header.** Undated documents
  pass the window; their count is printed.
* **An empty corpus read does not retire items.** Zero documents read skips
  the recompute, so a set whose material was deleted entirely stays until a run
  reads something.

## The run

* **`denial_loop` does not apply to arm B**: the endpoint has no conversation
  to continue. It applies to arms A and C.
* **Arm C depends on the endpoint's mode.** In `summary` mode there are no
  chunks to hand the model.
* **The price of context is relative to arm A** of a specific model; it can be
  compared between models, not between judges.
* **The manual chat path is not for the storefront**: the chat product has its
  own system prompt, the sample is small, temperature is uncontrolled.

## The models

* **The upstream serving a model is recorded, not pinned.** A router picks
  hosts per request (different quantisation, context windows);
  `syft-benchmark upstreams` shows the spread.
* **The shipped model catalogue is a snapshot** until refreshed. A model absent
  from it is still accepted.

## The report

* **The analyst's paragraph in the docx is written by a model** from the
  aggregated numbers only, and marked as such. The computed observations beside
  it are the measurement.
* **Different Spaces are not compared on accuracy**: each has its own corpus
  and questions. Read first what depends least on the corpus: inventions on
  questions without an answer, and abstention discrimination.
