# The data schema

Eleven tables in the benchmark's own Postgres (`db/models.py`, migrations in
`alembic/versions/`): four for the measurement, the rest for the service.

```mermaid
erDiagram
    QA_PAIRS ||--o{ RESULTS : "was assessed"
    RUNS ||--o{ RESULTS : "contains"
    JOBS ||--o{ RUNS : "opened"
    JOBS ||--o| RUN_AGGREGATES : "cached figures"
    TARGETS ||--o{ JOBS : "measured by"
    PROCESSED_UNITS

    QA_PAIRS {
        string id PK
        string space
        string collection
        string cohort "the question pool of one build"
        string job_id "the launch that built it; NULL from the CLI"
        string generator "ten keys"
        string task_type "extractive-choice-abstractive-negative"
        string doc_id "provenance"
        string chunk_id "the gold answer is checked against it"
        text question
        text answer "SENSITIVE: quotes the source"
        jsonb distractors
        text context
        jsonb meta "grading, key_facts, screening, writer call, entity check, article date"
        string expected_behavior "answer-abstain-correct_premise"
        string status "pending-active-rejected-retired"
        text status_note
        string status_reason "why not active"
        string model "the generator model"
        string question_hash "UNIQUE with space, generator, cohort"
    }
    PROCESSED_UNITS {
        string space PK
        string generator PK
        string unit_id PK "chunk_id or doc_id"
        string cohort PK
        string unit_kind "chunk or document"
        int pairs_made
    }
    RUNS {
        string id PK
        string space
        string endpoint
        string job_id "no FK; NULL from the CLI"
        string context_mode "closed_book-open_book-model_with_context"
        string context_source "what arm C is given"
        string profile "methodology profile"
        jsonb params "settings snapshot"
        string block "direct-denial_loop-monte_carlo"
        string model "this service's identifier"
        string model_vendor
        string model_sent_as "the name the provider was given"
        string model_provider "whose API answered"
        string model_build "the dated build behind the name"
        string judge_model
    }
    RESULTS {
        string id PK
        string run_id FK
        string qa_id FK
        string endpoint_response_type "raw-summary-both"
        text answer
        string verdict "correct-abstain-hallucinate-incomplete-pending-technical-web_sourced"
        text reasoning
        string expected_behavior "copy of the label at run time"
        boolean grounded "arms B and C"
        boolean retrieval_hit
        int retrieval_rank
        jsonb retrieved "SENSITIVE: chunks"
        jsonb extra "block results, text metrics"
        jsonb audit "SENSITIVE: whole prompts"
        string model
        string served_by "the upstream that answered"
        string judge_model
        string judge_served_by "the upstream that graded"
    }
```

| Table | What it holds |
| --- | --- |
| `qa_pairs` | the question set |
| `processed_units` | which chunk or document each generator has processed, per cohort |
| `runs` | one pass: arm × block × model, with its settings snapshot |
| `results` | one answer and its verdict; judges and hand verdicts add rows, never rewrite |
| `targets` | nodes under test: address, endpoint, index location, `instrument` and `probe` overrides, `enabled`, `schedule`, `schedule_at`, `next_run_at` |
| `jobs` | launches: `state`, `phase`, `kind`, `trigger`, progress, `params` (request and timing), `card`, `error` |
| `run_aggregates` | cached figures of one job; no row means recompute |
| `installation_settings` | the single (`id = 1`) row of installation overrides |
| `credentials` | sealed secrets: provider keys and Space tokens |
| `model_catalog` | one provider's model list per row, as a whole document |

---

## Decisions in the schema

### What was asked for, and what answered

* `runs.model` is this service's identifier (`anthropic/claude-sonnet-5`), the
  same whichever provider serves it.
* `model_sent_as`, `model_provider`, `model_build` record what was actually
  reached: the provider's name for the model and the dated build behind it.
* `results.served_by` / `judge_served_by` record, per answer, which upstream a
  router (e.g. OpenRouter) used — hosts differ in quantisation and context
  window. Recorded, not pinned. `syft-benchmark upstreams` reads them.

These are columns, not keys in `params`: `params` is compared for exact
equality to decide whether earlier answers count as done
([04-evaluation.md](04-evaluation.md)), and a build changing must not break
resuming.

### Other columns

* **`runs.context_mode`** — tells the arms apart; a string, so a new arm needs
  no migration.
* **`runs.context_source`** — arm C on raw chunks and arm C on the endpoint's
  finished answer measure different things.
* **`runs.profile`, `runs.params`** — how each row was obtained, so the report
  does not mix runs measured under different settings.
* **`qa_pairs.expected_behavior`** — on the pair: correct behaviour depends on
  the question, not the arm. Copied into `results`, since labelling can change.
* **`qa_pairs.status`** — `pending` (built, not screened), `active`,
  `rejected` (screened out), `retired` (left the window or a previous cohort).
  `status_reason`: `grounding`, `retrieval_gate`, `not_answerable`,
  `duplicate`, `owner`, `rotation`, `web_answerable`, `public_knowledge`,
  `wrong_language`, `ambiguous_entity`, `other`. Screened-out pairs are kept.
* **`qa_pairs.cohort` in the unique key** — the same question may repeat
  across cohorts (a rebuild over the same material).
* **`processed_units` keyed by generator and cohort** — each generator
  processes every chunk; a rebuild processes it afresh.
* **`results.endpoint_response_type`** — the endpoint mode at answer time.
* **`results.extra`** — per-block results (`denial`, `repeats`) and text
  metrics.
* **`retrieval_hit` / `retrieval_rank`** — for `raw` mode this is the
  measurement: whether and where the gold chunk was retrieved.
* **`results.audit`** — the prompts as sent.
* **Deleting a pair** (`db/pair_guard.py`) — refused once any result
  references it (`results.qa_id` cascades); retire it instead.
* **`jobs.card`** — the card built after measuring; replaced when the card is
  rebuilt with `record`. `card_outdated` is measured against it.
* **`targets.instrument` / `probe`, `installation_settings.values`** — sparse
  overrides, not snapshots, so a changed default reaches every target.
* **`model_catalog`** — read and written whole. The shipped
  `syft_benchmark/data/models.json` is used for any source with no row.

See [control-api.md](control-api.md) for how the service uses its tables.

---

## The database is a third copy of the corpus

`qa_pairs.answer` often quotes the source, `results.retrieved` holds chunks,
`results.audit` whole prompts. It must be protected like the corpus; see
[privacy.md](privacy.md).
