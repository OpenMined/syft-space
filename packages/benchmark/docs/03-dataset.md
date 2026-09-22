# Stage 3. Which set goes into the measurement

Every comparison in this measurement is between arms, between models, between
runs on different days. It rests on the compared parties having answered **one
and the same set of questions**. Meanwhile the set is alive: `generate` adds
items every cycle, screening takes pairs out of the active ones, the labelling
of the control half gets refined.

Hence three mechanisms, and they should not be confused:

| Mechanism | The question it answers | Where it is set |
| --- | --- | --- |
| **set mode** | what stays in the measurement over time | `generate --mode`, `--period` |
| **frozen slice** | which set is being measured right now | `freeze`, `evaluate --question-set` |
| **limit** | how much to take per run when there is no slice | `--limit` on `generate`, `evaluate`, `freeze` |

---

## Set mode

```bash
uv run syft-benchmark generate docs                       # incremental
uv run syft-benchmark generate docs --mode rolling -p 7d --max-pairs 200
uv run syft-benchmark generate docs --new-cohort -p 1m    # = rebuild, one-off
```

The corpus grows, and the measurement cannot grow along with it: three arms
across nine models multiply by every item. Sooner or later you choose not "how
much we can manage" but "what exactly we are measuring". The choice is
substantive, not technical: last year's document answers a question nobody asks
any more.

| Mode | The question it answers | What is in the measurement |
| --- | --- | --- |
| `incremental` | what new has appeared in the corpus | everything built, forever |
| `rolling` | what is current now | items from documents of the last N days |
| `rebuild` | **are the questions themselves any good** | the same material, the pool of questions built afresh |

| Setting | Default | What it does |
| --- | --- | --- |
| `dataset_mode` | `incremental` | What the set is like over time |
| `document_window_days` | `0` | The freshness window for documents; `0` — the whole corpus |
| `dataset_max_pairs` | `0` | The ceiling on active items; `0` — no ceiling |

The difference in cost is substantial: a rolling set reuses ready-made items
and calls the generator only for new material, whereas a rebuild pays for the
whole set again. So it is not scheduled for every night.

### The period

`--period` sets the span in all three modes and is written the human way:

| Notation | How many days | How it reads |
| --- | ---: | --- |
| `1d` | 1 | since yesterday |
| `7d`, `1w` | 7 | over a week |
| `2w` | 14 | over two weeks |
| `1m` | 30 | over a month |
| `1y` | 365 | over a year |
| `30` | 30 | a bare number — days |
| `0` | — | the whole corpus, no limit |

A month and a year are approximate, and that is deliberate: the period answers
the question "how long ago", not "since what date". Calendar precision would
add a difference of a day or two to a quantity that is set by eye in the first
place.

The count runs backwards from "now", not from midnight. For the nightly cycle
it makes no difference, and for a run in the middle of the day "since
yesterday" is more honestly read as "over the last 24 hours" than to guess that
a calendar day was meant.

An unreadable period is a refusal, not a default: silently taking the whole
corpus instead of a week is not the kind of mistake that gets forgiven, because
it costs a full generation pass.

The period takes effect differently, and the distinction matters:

* in `rolling` and `rebuild` it decides both **what to build from** and **what
  stays in the measurement**;
* in `incremental` — only what to build from: what has been built stays, an
  accumulating set being accumulating for a reason;
* on **any rebuild** — both `--mode rebuild` and `--new-cohort` on top of
  incremental mode — the period applies in full. A human named the span
  outright, and the set is obliged to keep within it: otherwise `--new-cohort
  --period 7d` would assemble a cohort over a week and then let it into the
  measurement mixed in with old material.

### Three decisions that hold the rolling set together

**What leaves is not deleted, and that is not caution.** An item carries the
verdicts of every previous run, and the foreign key `results.qa_id` is set with
a cascade: deleting a question means carrying off the history of measurements
along with it — precisely the thing the benchmark is kept for. So what leaves
is moved to `retired`: out of the measurement, not out of the database.
Screening (`rejected`) is a different matter: it is a verdict on the gold
answer, and such an item never comes back.

**What returns returns for free.** A one-week window, shifting by a day, keeps
six sevenths of yesterday's documents inside it. Building items over them again
would mean paying the generator for what has already been bought and getting
duplicates that the unique index would reject anyway. So recomputing the set is
not "delete and generate" but "recompute what is active": the generator is
called only where items do not yet exist.

**A document without a date is not cut off by the window.** The date is taken
from the ETL header — `published_date`, or `ingested_at` in its absence.
Publication matters more than ingestion: an interest in freshness is an
interest in when the material came into the world, whereas reindexing the
corpus shifts ingestion for everything at once and would thereby zero out any
window. The header is written by someone else's ETL and is not always written;
silently discarding an undated document would mean emptying the set because of
a foreign format, so it stays, and the number of such documents is printed —
otherwise "took a week's worth" would be an untruth nobody learned about.

**An empty corpus does not touch the set.** Zero documents read means not "all
the material has aged out" but that there was nothing to read: the collection
is empty, all the chunks are shorter than `min_chunk_chars`, the index is
being rebuilt. Recomputing over such an input would take every last item out of
the measurement, the next run would measure emptiness — and it would look like
the window's ordinary progress. A window that read the documents and found none
of them fresh is a different matter: that is its own decision, and it is
carried out.

### Volume

`--max-pairs` (`dataset_max_pairs`) sets the ceiling on active items. The
quantity is a total, so it is divided **round-robin across the generators**: an
item to each in turn, until either the budget or the items run out. A simple
"first N" would cut off the control half entirely — it is built later — and the
round-robin across generators does not allow that: each generator produces
items of exactly one half.

### What follows from this for the report

**The report describes the set that is in the measurement now.** Verdicts on
items that have been taken out remain in the database and in the audit export
but do not go into the shares: adding yesterday's cohort to today's would mean
computing a quantity over the union of two different measurements. `status`
shows both numbers — how many are in the measurement and how many have left it.

---

## Rebuilds and cohorts: are the questions themselves any good

```bash
generator_model=another-model \
  uv run syft-benchmark generate docs --new-cohort --period 7d
uv run syft-benchmark evaluate docs
uv run syft-benchmark cohorts docs -m closed_book --model vendor/m
```

The benchmark measures a model with questions it composed itself. That is its
structural weak spot, and there is no getting around it: a gold answer can be
inaccurate, a wording ambiguous, and the generator is of the same breed as the
models under test and errs in similar ways. Gold-answer screening catches some
such pairs, but it is lexical and judges grounding in the chunk, not the
sensibleness of the question.

There is nothing with which to answer "are the questions any good" directly: to
check questions you need other questions. Indirectly, you can.

**The idea.** We take THE SAME material and build a set over it afresh, as a
separate cohort. The corpus is the same, the endpoint is the same, the models
under test are the same, the judge is the same, the thresholds are the same.
Exactly one thing changes — the pool of questions. Then the difference in
numbers between cohorts is the contribution of the questions, and of nothing
else:

* **the numbers matched** — the questions are beside the point, and the
  difference between models speaks about the models;
* **the numbers diverged** — then they speak about the questions. Where to look
  is hinted at by the screening rate: a generator that had a third of its gold
  answers rejected probably did not build the other two thirds any better.

**A cohort** is one pool of questions built in a single pass. Its label is the
date and time of the build (`20260914-0300`); you can set your own with
`--cohort`. Its design rests on three decisions:

* **duplicates are forbidden within a cohort, not in general.** A question
  repeating between cohorts is legitimate and meaningful: it means the
  generator produced the same question from the same material — that is, it is
  stable. Had we forbidden such a repeat, rebuilds would be impossible: the
  second pass would be rejected wholesale by the unique index;
* **the processed mark also belongs to the cohort.** A rebuild is a fresh pass
  over the same material, and the previous build's mark must not stop it.
  Clearing `processed_units` is not needed for that: the new cohort simply has
  no marks, while the previous one keeps its own — and so it is reproducible;
* **the previous cohort is not deleted but taken out of the measurement.** Its
  items carry the verdicts of every run that went over it — the very thing the
  new one will be compared against. Deleting it would mean destroying the
  second half of the comparison.

Meanwhile there is always **one** pool in the measurement: two builds over the
same material would give two verdicts for one question, and the share would be
computed over the union of two different sets.

### Always state the span

Without it the set is rebuilt over the whole corpus — that is a full generation
pass, and on a live node usually not what was wanted; the command warns about
it.

But something more important than cost: **cohorts can be compared only at ONE
span.** A week's cohort and a month's cohort differ not only in their questions
but in their material, and a divergence in their numbers proves nothing — and
it is for that proof that a rebuild is done.

### What the comparison proves and what it does not

`cohorts` shows accuracy, inventions and the screening rate per cohort, and the
spread between them. **The divergence threshold is 10 points**, taken not from
the literature but from practice: up to ten points between sets over the same
material is the ordinary sampling spread; beyond that, with the material held
fixed, there is nothing left to explain it.

You look at the worse of the two spreads — accuracy and the share of
inventions. A set whose accuracy matched but whose share of inventions diverged
twofold is a diverged set too.

The caveat without which the comparison misleads: **two passes of ONE model
over one prompt reproduce its mistakes as well.** A match in the numbers then
means the reproducibility of the generator's decisions, not their correctness.
The check becomes convincing when the cohorts are built by DIFFERENT models —
and `cohorts`, together with the report, says so outright if there was only one
generator. The price of that independence is a second full generation pass.

---

## The frozen slice

```bash
uv run syft-benchmark freeze docs --out config/slice-docs.json --limit 60
uv run syft-benchmark evaluate docs --question-set config/slice-docs.json
```

As long as "which questions" is decided by selection on the fly, two runs take
different sets — and the difference in numbers between them means not what was
measured but that the set has grown. This is especially visible where the
comparison is the whole point of the measurement: arms A and C are obliged to
go over one set, otherwise "the price of context" is computed between different
halves.

The slice pins the list of `qa_id`s in order together with a **fingerprint** of
the question and the gold answer. Identifiers alone are not enough: a pair
survives regeneration, its text does not. The gold answer was refined, the
question reworded — the identifier is the same, the item is different, and the
answers collected relate to the previous one. The fingerprint turns that
substitution from silent into a refusal.

The gold answer enters the fingerprint on a par with the question: the judge
compares the answer against precisely that, and a fingerprint over the question
alone would let through a substitution of the thing being compared against.

Three rules:

* **a slice is the WHOLE selection.** `--limit` does not apply with it: the
  limit would select from what has already been selected and would bring back
  exactly the drift the slice exists to prevent;
* **a slice belongs to one Space.** Applying it to another node is a refusal,
  and `--strict-question-set` has nothing to do with it: these are different
  sets of questions;
* **rebuilding a slice makes sense for a NEW measurement.** In the middle of an
  ongoing one it means swapping the set out from under answers already
  collected.

| Setting | Default | What it does |
| --- | --- | --- |
| `question_set` | empty | The file of the frozen slice of questions |
| `strict_question_set` | `true` | A divergence between the set and the slice is a refusal |

`strict_question_set=false` lowers a divergence to a warning and throws
out the diverged items. The slice goes into the settings snapshot of every run
(`runs.params`), so a run over a slice and a run over the whole set are not
considered comparable and are not reused when resuming.

**A slice and a rolling set get in each other's way:** the slice pins the
questions, the rolling set changes them, and after the very first recompute the
slice will stop matching the set. Freezing makes sense within a single window —
for as long as the set has not moved.

---

## The limit

`--limit` exists on three commands, and everywhere it means one thing: **how
much to take from each generator**. Units, not percentages and not a grand
total.

| Command | Unit | `--limit 10` means |
| --- | --- | --- |
| `generate --limit` | chunks or documents | 10 units to process per generator |
| `evaluate --limit` | questions from the set | 10 questions per generator |
| `freeze --limit` | questions into the slice | 10 questions per generator |

**Why per generator rather than in total.** A generator is a distinct skill,
not a share of the sample: number masking measures precision about a figure,
`multihop_synthesis` the ability to connect two facts, `tiered_explanation` an
extended explanation, the control ones the ability to stay silent. The phrase
"the model is correct 71% of the time" only means something when all the skills
stand behind it, rather than those that happened to land in the sample.

A total limit divided among the generators would be a skew of two kinds at
once. By generator: ten items across ten generators — and half the skills are
not tested at all. By half of the set: if you divide by halves first, the two
control generators get as much as the eight ordinary ones, and two thirds of
the sample goes on testing silence.

A per-generator limit removes both. **The halves then survive on their own:**
each generator produces items of exactly one half (`unanswerable_property` —
unanswerable, `false_premise` — false premise, the other eight — answerable),
so having the generators represented entails having the halves represented.

The phase-3 limit in LiveTruth, from which all of this part is carried over, is
built the same way: there it is applied to each set separately and stratified
by news source. We have a single source — the Space's corpus — and the second
axis is not needed.

**The limit does not decide the composition of the set:** that is
`disabled_generators`'s job, at the generation stage. Selection by a
silent decision is the worst kind of configuration.

### One set of questions for everyone

**The selection is not random, and all models under test are asked the same
questions.** This is not a side property but the condition without which a
comparison of models means nothing: the difference in numbers would include the
difference in questions, with nothing to show for it.

It rests on three things:

* **there is not a single random decision in the selection.** Items are read
  from the database in a total order — by time, and by identifier on a tie —
  and the limit takes the first N from each generator. The identifier tiebreak
  is mandatory: the query is made anew for each run, that is, for each model
  under test, and under a partial order the database is free to return items
  with equal timestamps in a different order to different queries;
* **the limit takes a generator's EARLIEST items**, not its latest. So the set
  does not slide when `generate` adds new ones: the earlier ones stay in place,
  and tomorrow's run is comparable with today's;
* **the composition of the set does not change between model runs**: `evaluate`
  generates nothing, and the rolling set is recomputed only in `generate`.

What this does NOT guarantee is a match between launches on different days if
something changed in between: `generate` added items from a new generator,
screening took a pair out of the active ones, the freshness window moved part
of the set out. If the set has to be literally the same, it is frozen with a
slice.

### How much that is in absolute numbers

With ten generators enabled, `evaluate --limit 10` is **100 questions**: 80
answerable and 10 in each control half. From there they get multiplied by the
arms, the blocks and the models under test.

`generate` has the same multiplication, but the unit is different and a unit
yields several items. At the defaults (`pairs_per_chunk=2`), `--limit 10`
gives this:

| Group | Units | Items per unit | Total |
| --- | ---: | ---: | ---: |
| masking (3 categories in one pass) | 10 chunks | 6 | 60 |
| `mcq` | 10 chunks | 2 | 20 |
| `two_truths_one_lie` | 10 chunks | 2 | 20 |
| `qa` | 10 chunks | 2 | 20 |
| `unanswerable_property` | 10 chunks | 2 | 20 |
| `false_premise` | 10 chunks | 2 | 20 |
| `multihop_synthesis` | 10 documents | 2 | 20 |
| `tiered_explanation` | 10 documents | 1 | 10 |
| | | | **≈190 candidates** |

Candidates, not items: each goes through screening — grounding of the gold
answer in the chunk for the ordinary ones, live retrieval for the control ones
— and not all of it reaches the set. How much did is printed by the command
itself: "items 190 (fit 164, screened out 26)".

Next — [stage 4: the run](04-evaluation.md).
