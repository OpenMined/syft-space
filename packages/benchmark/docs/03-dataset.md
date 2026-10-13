# Stage 3. Which set goes into the measurement

Comparisons between arms, models and days only mean something over the same
questions, while the set keeps changing: `generate` adds items, filtering
rejects some, the window moves. Three mechanisms control this:

| Mechanism | The question it answers | Where it is set |
| --- | --- | --- |
| **set mode** | what stays in the measurement over time | `generate --mode`, `--period`, `--max-pairs` |
| **frozen slice** | exactly which questions are measured now | `freeze`, `evaluate --question-set` |
| **limit** | how much to take per generator when there is no slice | `--limit` on `generate`, `evaluate`, `freeze` |

---

## Set mode

```bash
uv run syft-benchmark generate docs                       # incremental
uv run syft-benchmark generate docs --mode rolling -p 7d --max-pairs 200
uv run syft-benchmark generate docs --new-cohort -p 1m    # a one-off rebuild
```

| Mode | The question it answers | What is in the measurement |
| --- | --- | --- |
| `incremental` | what is new in the corpus | everything built, accumulating |
| `rolling` | what is current | items from documents of the last N days |
| `rebuild` | are the questions themselves any good | the same material, a fresh pool of questions (new cohort) |

| Setting | Default | What it does |
| --- | --- | --- |
| `dataset_mode` | `incremental` | How the set behaves over time |
| `document_window_days` | `0` | Freshness window in days; `0` — the whole corpus |
| `dataset_max_pairs` | `0` | Cap on active items; `0` — no cap |
| `top_up_max_usd` | `5.0` | USD a build may spend on the top-up ([02-generation.md](02-generation.md#the-pipeline)); `0` — no top-up |

A rolling set reuses existing items and calls the generator only for new
material; a rebuild pays for the whole set again.

### The period

`--period` (`-p`) sets `document_window_days`:

| Notation | Days |
| --- | ---: |
| `1d` | 1 |
| `7d`, `1w` | 7 |
| `2w` | 14 |
| `1m` | 30 |
| `1y` | 365 |
| `30` | 30 (a bare number is days) |
| `0` | no window |

Counted back from now, not from midnight. An unreadable period is an error.

How the window applies:

- in every mode it limits which documents items are **built** from;
- in `rolling` and `rebuild`, and on any `--new-cohort`, it also takes items
  from older documents **out of the measurement**;
- in `incremental` without a rebuild, built items stay.

### Recomputing the set

After `generate` and after a `filter` pass that made pairs active, the set is
recomputed:

- **Only the current cohort is active.** Older cohorts' items are retired.
- **The window** (where it applies) retires items whose document left it, and
  brings back retired items whose document is inside it again — without a
  generator call.
- **The cap** (`dataset_max_pairs`) is divided round-robin across generators.
  Pairs that passed the web check fill it first. Within a generator: in
  rolling/rebuild the newest document first, otherwise items already active
  first, then the oldest.
- Items that leave become `retired` (`status_reason = rotation`), never
  deleted: results reference them with a cascading foreign key. `rejected` is
  not touched by recomputing.
- A document's date is the ETL header `published_date`, else when it was
  added to the Space, else `ingested_at`. The header comes from the chunks'
  `doc_*` metadata; indexes built before the Space wrote it keep the header
  at the start of chunk 0, where it is cut off and read.
  Undated documents are not cut by the window; their count is printed.
- If no documents were read (empty collection, index rebuilding), the set is
  left as it is.
- A build that was stopped does not recompute the set.

The report covers only the items in the measurement now; verdicts on retired
items stay in the database and audit export. `status` shows both counts.

---

## Rebuilds and cohorts

```bash
uv run syft-benchmark settings set generator_model another/model
uv run syft-benchmark generate docs --new-cohort --period 7d
uv run syft-benchmark evaluate docs
uv run syft-benchmark cohorts docs -m closed_book --model vendor/m
```

A rebuild builds a fresh pool of questions over the same material, as a
separate cohort. With corpus, endpoint, models, judge and thresholds fixed,
the difference in numbers between cohorts is the contribution of the
questions.

A **cohort** is one pool built in one pass, labelled with the build time
(`20260914-0300`) or `--cohort <name>`.

- Duplicates are forbidden within a cohort, allowed across cohorts.
- `processed_units` marks are per cohort, so a rebuild re-reads all material.
- The previous cohort is retired, not deleted: its verdicts are what the new
  one is compared against.

**Always pass `--period` to a rebuild.** Without it the whole corpus is
regenerated (the command warns). Cohorts are comparable only at the same span.

`cohorts` shows accuracy, inventions and the rejection rate per cohort and
the spread between them. Cohorts **diverge** when the larger of the accuracy
spread and the invention-share spread exceeds **10 points**. Two cohorts from
one generator model reproduce its mistakes too; `cohorts` and the report say
so when only one generator model was used — build the second cohort with a
different `generator_model`.

---

## The frozen slice

```bash
uv run syft-benchmark freeze docs --out config/slice-docs.json --limit 60
uv run syft-benchmark evaluate docs --question-set config/slice-docs.json
```

A slice pins an ordered list of `qa_id`s with a fingerprint of each question
and gold answer, so a reworded item under the same id is detected. It is built
from active pairs that pass the web check gate
([02-generation.md](02-generation.md#the-web-check)).

- **A slice is the whole selection**: `--limit` does not apply with it.
- **A slice belongs to one Space**; using it on another node is refused.
- **Rebuild a slice only for a new measurement.**

| Setting | Default | What it does |
| --- | --- | --- |
| `question_set` | empty | The slice file |
| `strict_question_set` | `true` | A mismatch between the set and the slice is a refusal |

With `strict_question_set=false` a mismatch is a warning and the mismatched
items are dropped. The slice is part of `runs.params`, so runs with and
without it are not comparable and are not reused on resume.

A rolling set moves under a slice; freeze within one window.

---

## The limit

`--limit` always means **per generator**:

| Command | `--limit 10` means |
| --- | --- |
| `generate` | budget of `10 × pairs_per_chunk` items per generator (replaces `chunks_per_run`) |
| `evaluate` | 10 questions per generator |
| `freeze` | 10 questions per generator in the slice |

Per generator, not total: each generator is a distinct skill, and a total
limit would leave some untested or overweight the two control generators. Each
generator produces items of exactly one half (answerable, unanswerable, false
premise), so all halves are represented. Which generators exist in the set is
decided by `disabled_generators`, not by the limit.

### Selection

- Candidates are active pairs that pass the web check gate.
- They are ordered by creation time **newest first**, ties by id — a total
  order, so every model in a launch gets the same questions.
- The limit takes the first N per generator, i.e. the newest.
- `evaluate` neither generates nor filters; the set changes only in
  `generate` and `filter`.

Between launches the selection changes as items are added, rejected or
retired. For a literally identical set, use a slice.

### Numbers

With all ten generators, `evaluate --limit 10` is up to **100 questions**:
80 answerable, 10 unanswerable, 10 false premise — then multiplied by arms,
blocks and models.

`generate --limit 10` at `pairs_per_chunk=2` writes up to 20 items per
generator, **200** in total, all `pending` until filtering
(`tiered_explanation` gives one item per document, so it reads up to 20
documents). The command prints units read, items written, duplicates and
failures.

Next — [stage 4: the run](04-evaluation.md).
