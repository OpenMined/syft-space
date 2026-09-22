# Known limitations of the methodology

The things this measurement cannot do, or can do only conditionally. The list
is kept deliberately: a number that does not come with a statement of what it
does not mean gets read more broadly than it should be.

---

## On judging

* **The judge is a model.** The divergence between judges is measurable with a
  panel and named as a number — the share of questions on which two issued one
  verdict — but the assessment has no absolute scale: high agreement means the
  judges are alike, not that they are right. Hence the rule: without the
  judge's name the numbers are unreadable, and it is stated in the report and
  goes into the published dictionary.
* **A console judge judges only the direct test.** Pressure and repeats issue
  their verdicts as they go, and cannot be judged after the fact: the judge did
  not see the rounds.
* **A human's verdict cannot be rechecked the same way a machine's can.** This
  is marked in the audit record.
* **Text metrics know nothing of correctness.** BLEU and ROUGE measure word
  overlap: a retelling in one's own words gets a low score with a correct
  answer, a verbatim quotation off the point gets a high one. They are off by
  default, enter no share, and are meaningful only for comparison within a
  single report.

## On the set

* **Gold-answer screening is lexical.** It is deterministic and cheap, but a
  paraphrased gold answer that legitimately rests on the chunk may fall short
  of the coverage. Confirmation by a second model remains a possible extension;
  starting with it would mean judging a generator with a generator.
* **The control set's labelling is relative and not free.** "There is no
  answer" is meaningful only with respect to a specific endpoint; the gate
  decides with a model and costs a call per candidate. A gate error on the side
  of strictness screens out a fit negative — that is cheaper than accusing a
  model of invention where an answer did exist.
* **The document-level generators are heavy for a small model.** On a local 4B
  `multihop_synthesis` and `tiered_explanation` break down into invention;
  screening catches it, but the time has been spent.
* **Comparing cohorts built by one generator proves nothing.** Two passes of
  one model over one prompt reproduce its mistakes as well: a match means the
  reproducibility of the decisions, not their correctness. An independent check
  requires a second generator and a second full generation pass.
* **A frozen slice is no protection against a change of corpus.** It pins the
  questions, not the node's contents: reindexing the Space changes the answers
  while leaving the items the same. A slice makes the sample comparable, not
  the rig. It also conflicts with a rolling set in substance: one pins the
  questions, the other changes them.
* **A rolling set makes runs on different days non-comparable line by line.**
  That is not a defect but its point: what is measured is what is fresh, and
  yesterday's share related to a different cohort of questions. What can be
  compared between days is behaviour — the share of abstentions, the price of
  context — not accuracy on a particular set.
* **The freshness window relies on someone else's header.** The date comes from
  the node's ETL; an incomplete or unparsed header means "there is no date",
  and the window lets such a document through. The number of such documents is
  printed, but the benchmark cannot fix their format.
* **An empty corpus does not take items out of the measurement.** Zero
  documents read is a state of the rig, not a sentence on the set, and a
  recompute over it is skipped. The price of that decision: a set whose
  material really was deleted from the collection entirely will stay in the
  measurement until the first run that reads something.

## On the run

* **`denial_loop` is not applicable to arm B** by the design of the endpoint's
  API, and that is not an omission: a single-shot request has no conversation
  to continue. It is applicable to arms A and C — there a model does the
  answering.
* **Arm C depends on the endpoint's mode.** On `summary` the chunks are
  unavailable in principle: not our limitation but the owner's decision, and
  there is no getting around it.
* **The price of context is measured relative to arm A**, that is, relative to
  a specific model under test. It can be compared between models; between
  different judges, no.
* **The manual path is not for the storefront.** This is about a console
  MODEL: a product with its own system prompt does the answering, the sample is
  small, there is no temperature.

## On the models

* **The upstream that serves a model is not pinned.** A router chooses between
  hosts per request — the same weights at fp4 and at bf16, context windows an
  order of magnitude apart — and any of those changes what a model answers. The
  host is recorded per answer (`syft-benchmark upstreams`) and nothing more:
  pinning one costs a run whenever the pinned host is down, and that price is
  not worth paying until the records show the spread matters.
* **The model catalogue is a snapshot.** It ships with the code and is a copy
  of a provider's list as of the day it was taken, so an installation raised
  from an old image offers the models of that day until somebody refreshes it.
  A model absent from it is still accepted — the catalogue is a way of getting
  a name right, not a list of what may be measured.

## On the report

* **The analyst's paragraph in the document is written by a model.** It rests
  on the report's aggregated numbers alone and is marked as written by a model,
  but it is checked against the tables above it rather than on its own: it is a
  retelling, not a measurement. The report is complete without it — the
  observations beside it are computed.
* **Different Spaces are not compared on accuracy.** Each has its own corpus,
  and therefore its own questions. What barely depends on the corpus's
  difficulty is inventions on questions without an answer and abstention
  discrimination — those are the ones that should be read first.
