# Stage 7. The audit log

```bash
uv run syft-benchmark audit docs --out reports/audit.jsonl
uv run syft-benchmark audit docs --out reports/audit.md      # for reading by eye
uv run syft-benchmark audit docs --judge openai/gpt-4.1      # one judge
uv run syft-benchmark audit docs --job <id>                  # one launch
uv run syft-benchmark audit docs --no-context                # chunk texts and prompts cut out
```

The benchmark's numbers are shares of a judge model's verdicts on text that is
not in the report. The audit export hands out the raw records so the owner, or
an auditor they bring in, can recheck them. It is not part of the daily cycle.

---

## What is recorded

`results.audit` is written beside every answer during the run (with
`audit_log=true`, the default); it cannot be rebuilt later because prompts
depend on the settings of the moment.

* `responder_system`, `responder_prompt` — the answerer's prompts; in arm C the
  prompt includes the material verbatim, and `context` repeats it (cut to
  `audit_max_chars`);
* `context_source`;
* `call` — `finish_reason`, `truncated`, `length_retry`, `length_retries`,
  `attempts`, `reused`, `cost_usd`, and the web search fields `web_search`,
  `web_search_via`, `web_search_forced`, `web_search_requests`,
  `web_search_retry` (why the call was asked again with the Exa plugin);
* with web search, `citations`, `web_search_unused` and
  `web_search_unused_reason`;
* `judge_system`, `judge_prompt`, `judge_raw` (the reply before parsing),
  `judge_call` (cost, latency);
* `judged_without_model: true` when no judge was called (regex abstention,
  option letter or fill-in span match), `judged_by_console: <name>` for a
  verdict imported from a chat, `judged_by_owner` for an owner override.

`results.extra` keeps the block transcripts: every `denial_loop` round
(objection, answer, judge prompt and reply) and every `monte_carlo` trial.

A later verdict on the same answer (owner override, chat or deferred
judging) is a new row with the answer side of the audit record and the block
outcomes; the original judge's call and the block transcripts stay on the row
that ran them.

---

## The export

One record per question, JSON Lines (or Markdown when `--out` ends in `.md`):

* the item: question, gold answer, distractors, generator, expected behaviour;
* provenance: document, chunk and the source chunk text, status and screening
  note, the model that built it, its `meta`;
* `answers` — both arms side by side, the **latest** answer per (arm, block,
  answerer, judge): answer, verdict, reasoning, judge, grounding, retrieval
  hit/rank and the retrieved chunks, block transcripts, the audit record, and
  the run's id, profile and settings snapshot.

One launch's records, writer calls that dropped drafts or failed included,
are also in its Excel export (`GET /console/report/runs/{job}/export.xlsx`,
[control-api.md](control-api.md)).

`--job` limits the export to one launch (its id from the job history), so
answers obtained under different settings are not mixed. `evaluate` from the
CLI belongs to no launch; imported verdicts (`import-judging`) are recorded
under the launch whose answers they grade.

Records without prompts (`audit_log=false`) are counted in the command's
output; such verdicts can only be rechecked by a new run.

---

## The log contains corpus text

The export carries retrieved chunks and gold answers that quote the source:
handle it like the corpus
([privacy.md](privacy.md#3-the-database-is-protected-like-the-corpus)).
`--no-context` removes the chunk texts (`context`, retrieved chunks, source
chunk) and replaces `responder_prompt` and `judge_prompt` with
`[cut out: --no-context]`; questions, gold answers, answers and judge replies
stay, and a verdict cannot be rechecked from such an export.

| Setting | Default | What it does |
| --- | --- | --- |
| `audit_log` | `true` | Write prompts and judge replies beside every answer |
| `audit_max_chars` | `20000` | Ceiling on the stored arm C `context` |
