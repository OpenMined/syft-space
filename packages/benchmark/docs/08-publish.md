# Stage 8. Publishing

```bash
uv run syft-benchmark publish docs --dry-run   # show the payload, send nothing
uv run syft-benchmark publish docs
uv run syft-benchmark retract docs
```

The benchmark does not talk to SyftHub. It hands the card to the Space that
owns the endpoint (`POST {url}/api/v1/endpoints/{endpoint}/quality`, with the
Space's token), and the Space publishes it under its own account
([invariant 5](privacy.md)). `retract` calls `DELETE` on the same route; the
Space decides who may retract.

Publishing is a separate step (or the end of a control-API job with
`publish: true`). The CLI publishes the card of the launch that owns the
Space's newest run; a run from the CLI belongs to no launch, and then the card
describes the node as of now.

---

## Only aggregates leave the perimeter

Shares, counters, identifiers and codes. No published string value contains a
space — they are all names of models, generators, modes and profiles, while
corpus text always has spaces. A test locks the payload's composition
([invariant 3](privacy.md)).

```json
{"version": 2, "kind": "retrieval", "arm": "model_with_context", "job": "...",
 "checked_at": "...", "score": 0.82, "fabrication_rate": 0.04,
 "reliable": true, "samples": 515,
 "answerable":   {"samples": 412, "correct": 0.71, "abstain": 0.12,
                  "hallucinate": 0.17, "lmi": 0.19},
 "unanswerable": {"samples": 103, "fabricated": 0.04, "web_sourced": 2},
 "pressure":  {"samples": 25, "flip_rate": 0.2, "held": [0.92, 0.84, 0.8]},
 "stability": {"samples": 30, "consistency": 0.91,
               "by_temperature": [{"temperature": 0.3, "accuracy": 0.9},
                                  {"temperature": 0.9, "accuracy": 0.7}]},
 "discrimination": 0.63, "retrieval": 0.82,
 "models": [{"model": "...", "samples": 412, "accuracy": 0.78,
             "fabrication": 0.02, "lmi": 0.1, "context_gain": -0.05,
             "closed_accuracy": 0.12}],
 "skills": [{"generator": "mcq", "samples": 80, "accuracy": 0.9}],
 "trust": {"judges": 3, "agreement": 0.86, "consistency": 0.91,
           "even_coverage": true, "failed": 0, "pending": 0, "flags": []},
 "dataset":    {"mode": "rolling", "window_days": 7, "cohort": "...",
                "questions": 515},
 "instrument": {"profile": "default", "judge": "...", "judges": 3,
                "subjects": 9}}
```

`version` (2) tells the Space what it is reading; a Space that does not know it
answers 422 and the card is not sent.

Every figure counts each answer's counted verdict: the owner override, else
the primary judge's (`instrument.judge`), else the next judge's in panel order
([05-judging.md](05-judging.md)). `trust.judges` counts judges, not overrides.

The headline numbers come from the `direct` block. `pressure` (from
`denial_loop`: the flip rate and the share still standing after each round)
and `stability` (from `monte_carlo`: consistency and accuracy per temperature)
are present only when those blocks ran. Their questions and answers never
leave.

---

## The kind of product sets the headline number

The kind is read from the endpoint modes recorded in the results: `summary` or
`both` — `answering`; only `raw` — `retrieval`.

| Kind | Arm | `score` | `fabrication_rate` |
| --- | --- | --- | --- |
| `answering` | B `open_book` | accuracy of the endpoint's answer | inventions on the no-answer half |
| `retrieval` | C `model_with_context` | retrieval hit rate | inventions on the no-answer half |

Arm B is not run ([04-evaluation.md](04-evaluation.md)), so an answering card
is built only from stored arm B results; with none, there is nothing to
publish.

For `retrieval` the headline figures are those of the best-scoring model under
test. `models` lists every model by name (accuracy with the endpoint's
material, `closed_accuracy` without it, fabrication, LMI, `context_gain`);
they are never averaged, so adding a model to the config cannot move the
node's numbers.

---

## `reliable` is a gate

`reliable` is false when any of these holds:

| Code in `trust.flags` | Condition |
| --- | --- |
| `few_samples` | fewer than 30 graded answers (both halves) |
| `judges_disagree` | judge agreement below 0.7 |
| `uneven_coverage` | an item type lags the best by more than 25% of its graded count |
| `pending_verdicts` | some answers have no verdict |

`failed_calls` is also flagged but does not affect `reliable`. Reasons go out
as codes; the storefront writes its own wording.

---

## Comparability

`instrument` (profile, primary judge, panel size, number of models under test)
lets the storefront tell installations apart: Spaces measured by one
installation share judges and models, different installations guarantee
nothing. `dataset` names the set behind the number (mode, window, cohort,
questions).

Each Space has its own corpus and questions, so accuracies of two Spaces also
compare the difficulty of their sets. Inventions on the no-answer half and
abstention discrimination depend least on difficulty — read them first.

---

## A refusal from the Space is not a failure

| Space answer | Meaning |
| --- | --- |
| 404 | `benchmarks_mode` is off or the Space is too old: the owner has not consented |
| 422 | the Space does not accept card version 2 |
| 2xx | `stored` and the number of marketplaces delivered to are reported |

A card with no graded answers is not sent. In a control-API job the card is
built before publishing and stays on the job (`JobView.card`) whether or not
the Space accepted it ([control-api.md](control-api.md)).

This is the last stage. Launching all of it from the Space's UI —
[control-api.md](control-api.md).
