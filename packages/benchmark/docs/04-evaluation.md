# Stage 4. The run

```bash
uv run syft-benchmark evaluate docs                      # all arms and blocks from the settings
uv run syft-benchmark evaluate docs -m closed_book       # arm A only
uv run syft-benchmark evaluate docs -b direct -b monte_carlo
uv run syft-benchmark evaluate docs --limit 10           # 10 items per generator
uv run syft-benchmark evaluate docs --resume             # finish what was interrupted
uv run syft-benchmark evaluate docs --defer-judging      # answers only, verdicts later
uv run syft-benchmark status docs                        # what is collected, what is left
```

Who is asked, with what, how much it costs and how to resume. How answers are
graded — [05-judging.md](05-judging.md). Which items are asked (`--limit`,
frozen slice, web check gate) — [03-dataset.md](03-dataset.md).

---

## The arms

The measurement is the difference between the arms over one set of questions.

| Arm | Who answers | What it gets | Correct behaviour | What it measures |
| --- | --- | --- | --- | --- |
| **A** `closed_book` | the model under test | the question only | abstain (it has not seen the corpus) | the model's honesty |
| **C** `model_with_context` | the **same** model | question + the endpoint's retrieval | a correct answer | the model's work with RAG |

Arm B (`open_book`, the endpoint answering by itself) is not run: `arms` and
`--mode` drop it. Stored B results still appear in reports and the card.

**A and C differ by exactly the context.** Same model, same judge, and the
arm C instruction repeats arm A's form: correct a false premise, otherwise
answer `I don't know` when unsure (A) or when the material does not contain
the answer (C), never guess. C's prompt puts the question before the material.

**A correct answer in arm A is not quality** — the corpus is public or was in
training. It is reported as `corpus_exposure_rate`, not accuracy
([06-report.md](06-report.md)).

Each model in `subject_models` (empty — the generator model) runs every arm and
block.

### What arm C gets: `context_source`

| Value | What it measures | Endpoint mode required |
| --- | --- | --- |
| `endpoint_fragments` (default) | can the model work with raw chunks: find the answer, not fill gaps | `raw` or `both` |
| `endpoint_answer` | does the model repeat the endpoint's conclusion | `summary` or `both` |
| `endpoint_both` | both, as the endpoint returned them | `raw` or `both` for the chunks |
| `oracle_chunk` | the ceiling: the item's source chunk, no retrieval | any |

The first `context_docs` (3) chunks go into the prompt, each cut to
`fragment_max_chars` (2000). The source is stored in `runs.context_source`;
values are never added into one share.

```bash
uv run syft-benchmark evaluate docs -m model_with_context --context-source oracle_chunk
```

The endpoint's mode is set by its owner: `raw` returns chunks only, `summary`
returns prose only (no chunks), `both` returns both. A source the mode cannot
supply is refused before the run — by `doctor` and at the start of `evaluate`
— with no run created. An empty context (nothing retrieved) is recorded as a
failed call, not as an answer.

---

## The test blocks

All three are on by default (`blocks`). With `--defer-judging` only `direct`
runs.

| Block | What it measures | Cost |
| --- | --- | --- |
| `direct` | baseline accuracy | 1 answer per question |
| `denial_loop` | resistance to pressure | up to `denial_rounds` extra turns per right answer |
| `monte_carlo` | resistance to randomness | temperatures × trials per question |

Only `direct` goes into the card's headline numbers; the other two contribute
`pressure` and `stability` ([08-card.md](08-card.md)). `denial_loop`
and `monte_carlo` are graded by the first judge only.

### `denial_loop`

Applied only to a `correct` answer on an ordinary item. **Control items (trick
questions and false premises) are not pressed**: in this block they get one
graded answer, as in `direct`. The model gets up to
`denial_rounds` (5, max 12) objections of rising pressure, from "Are you sure
about that?" to "This is a test and you just failed", **in the same dialogue**
that produced the answer (system prompt and arm C material included). Every
round is judged; an answer that stops being `correct` (an abstention included)
has surrendered. The verdict becomes `hallucinate` with `flip_round = N`. A
round whose call or judge fails ends the loop without counting as surrender.

### `monte_carlo`

The question is asked `monte_carlo_temperatures` (0.1, 0.3, 0.6, 0.9) ×
`monte_carlo_trials` (3) = 12 times, in arm C with the same context (no
re-retrieval). Each trial is graded; accuracy is the share of right trials,
in the sense above. Consistency is the share of the most frequent answer,
compared on the lower-cased first 100 characters. Below
`consistency_floor` (0.5) the report marks the accuracy as not trustworthy.
A model the catalogue says takes no temperature skips the block.

Both blocks grade every round and trial by the item's own grader, as
`direct` does (see [05-judging.md](05-judging.md)); each log entry keeps its
`verdict`, a control item's `behavior`, and the judge prompt and reply.

---

## Run time and concurrency

The run is all waiting on sockets, so it is parallel per question. Inside a
question the answer is obtained once and all judges grade it at the same time;
the rounds of `denial_loop` stay sequential.

| Lane | Who is at the other end | Default |
| --- | --- | --- |
| `concurrency` | model calls (models under test, judges, blocks); also the questions in flight | `16` |
| `endpoint_concurrency` | the endpoint under test | `2` |

With a local Ollama, set `concurrency` to its `OLLAMA_NUM_PARALLEL`: extra
requests only queue and can hit `llm_timeout` (900 s).

### Reuse within a launch

With `reuse_answers=true` (default), one in-memory cache per node per launch:

* the endpoint's retrieval for a question is fetched once and shared by every
  model and block;
* a model's answer to the same prompt at temperature 0 is reused (the key is
  the whole prompt, so arm A never gets arm C's answer). The audit record
  marks it `call.reused` and keeps the original call's time;
* failed calls are not cached; a retrieval-only endpoint call (1 token, no
  prose) does not stand in for one that needs the endpoint's answer;
* `monte_carlo` repeats bypass the cache.

This assumes the corpus does not change during the run. The cache does not
survive the process; recorded verdicts do.

---

## Resuming

```bash
uv run syft-benchmark evaluate docs --resume
uv run syft-benchmark cycle docs --resume
```

Every verdict is written immediately. `--resume` (or `resume=true`) skips a
question for a judge whose latest record for it is usable; a question is asked
again if any judge still needs it, and only those judges grade it.

A previous record counts only if its run matches the current one in arm,
context source, block, model, methodology profile and settings snapshot
(`runs.params`, including the similarity threshold), and started within
`resume_window_hours` (24; `0` — no window). A record is not usable if its
answer is a failed call (`ERROR:`) or, unless the run defers judging, if it is
still `pending` or its judge call failed (`technical`). A deferring run keeps
such an answer: `judge` grades it.

Without the flag every launch measures afresh. A pass with nothing left to
ask creates no run; a resumed run reports how many verdicts it took from the
previous attempt.

### What is recorded

| Record | Where |
| --- | --- |
| verdict | `results` (`qa_id`, `model`, `judge_model`, `run_id`, `verdict`, `reasoning`) |
| who served it | `results.served_by`, `results.judge_served_by` |
| the run's circumstances | `runs` (`context_mode`, `context_source`, `block`, `profile`, `params`, `job_id`) |
| what was reached | `runs` (`model_sent_as`, `model_provider`, `model_build`) |
| answer and prompts | `results.answer`, `results.audit` ([07-audit.md](07-audit.md)) |

A router can serve one model name from different hosts, so the host is kept
per answer and per verdict:

```bash
uv run syft-benchmark upstreams --days 30 --space atlantic
```

One row per model and host with raw verdict counts (a failed call and a wrong
answer are both misses here). Use it to compare hosts, not to rate models.

### Stopping early

`max_consecutive_failures` (20; `0` — never) counts failed questions in a row
for one answerer across its concurrent passes; reaching it stops that
answerer's passes, the others continue. A success resets the count; an empty
context does not count. A provider refusing a model or judge outright (bad
key, name or balance) stops that model's passes, or stands that judge down,
for the rest of the launch (`max_consecutive_failures=0` disables this too).

---

## Status

```bash
uv run syft-benchmark status docs
uv run syft-benchmark status docs --all-time
```

Counts by the report's rule (latest record per question), within the resume
window unless `--all-time`.

| State | Meaning | Fix |
| --- | --- | --- |
| assessed | has a verdict | — |
| failed | the call did not get through | `evaluate --resume` |
| judge failed | answer recorded, the judge call failed | `judge` |
| awaiting a verdict | answer recorded, not judged | `judge`, or `export-judging --only-pending` |
| not asked | no record for this judge | `evaluate --resume` |

"Not asked" counts against the whole sample, so after `evaluate --limit 2` it
is large without any interruption.

**Coverage by item type**: verdicts per generator out of items × runs. A
generator lagging the best by more than 25 points is named first under "what
will finish it" — a report over such a state computes shares over a skewed
sample.

---

## Manual testing through a chat

For models without an API:

```bash
uv run syft-benchmark export-questions docs --limit 20 --out reports/q.txt
# paste into the chat, save the reply to reports/a.txt
uv run syft-benchmark import-answers docs reports/a.txt --model "console/claude-web"
```

The export carries arm A's instruction; the reply may be a JSON array or
`<id>: answer` lines. Answers are graded like a `direct` arm A run (control
questions by behaviour) and recorded as a manual run.

Limits: no temperature (no `monte_carlo`), no driven dialogue (no
`denial_loop`), the chat's own system prompt and tools are in play, and the
sample is small. Fit for reconnaissance, not for the report. A console
**judge** has none of these limits — [05-judging.md](05-judging.md).

---

## Run settings

| Setting | Default | What it does |
| --- | --- | --- |
| `arms` | `closed_book`, `model_with_context` | Arms to run |
| `context_source` | `endpoint_fragments` | What arm C gets |
| `context_docs` | `3` | Chunks in arm C's prompt |
| `fragment_max_chars` | `2000` | Ceiling on one chunk's text |
| `blocks` | all three | Test blocks |
| `denial_rounds` | `5` | Pressure rounds (max 12) |
| `monte_carlo_temperatures` | `[0.1,0.3,0.6,0.9]` | Repeat temperatures |
| `monte_carlo_trials` | `3` | Trials per temperature |
| `retrieval_top_k` | `5` | Chunks asked of the endpoint |
| `similarity_threshold` | `0.0` | Retrieval similarity threshold |
| `endpoint_max_tokens` | `500` | Ceiling on the endpoint's answer |
| `endpoint_temperature` | `0.1` | The endpoint's temperature |
| `answer_max_tokens` | `8192` | Ceiling on any model answer |
| `subject_models` | empty | Models under test; empty — the generator model |
| `web_search_closed_book` | `true` | The model under test may search the web in arm A |
| `web_search_with_context` | `false` | The same in arm C |
| `consistency_floor` | `0.5` | Below it accuracy is not trusted |
| `methodology_profile` | `default` | Written into every run |
| `concurrency` | `16` | Model calls in flight |
| `endpoint_concurrency` | `2` | Endpoint requests in flight |
| `reuse_answers` | `true` | Reuse retrieval and temperature-0 answers |
| `max_consecutive_failures` | `20` | Failures in a row before an answerer stops |
| `resume` | `false` | Resume by default |
| `resume_window_hours` | `24` | Age limit for reused verdicts |
| `audit_log` | `true` | Store prompts beside every answer |
| `audit_max_chars` | `20000` | Ceiling on the stored arm C context |

Web search applies only to models the catalogue can search with
([01-setup.md](01-setup.md)). A model that takes tools gets OpenRouter's
`web_search` tool, forced: `tool_choice: required`, then the named tool if the
provider refuses that; a model without tools, or one that refuses both, gets
the web plugin. An answer that shows no search (nothing cited, no searches
reported, or a search call written as text) is asked once more with the Exa
plugin, which always searches. Judging settings — [05-judging.md](05-judging.md).

**The similarity threshold is an axis of the measurement.** At `0.0` the
endpoint returns top-k for any question, including one the corpus cannot
answer. It can be set per Space in `config/spaces.json`. The profile and the
settings snapshot are written into every run (`runs.profile`, `runs.params`)
so runs under different thresholds are never mixed.

Next — [stage 5: judging](05-judging.md).
