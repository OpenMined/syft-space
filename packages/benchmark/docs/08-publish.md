# Stage 8. Publishing

```bash
uv run syft-benchmark publish docs
uv run syft-benchmark retract docs
```

The benchmark does not go to SyftHub. It hands the numbers to the Space that
owns the endpoint, and the Space publishes them under its own account —
exactly as it already does with health. There are no hub credentials here and
there must not be; this is [invariant 5](privacy.md).

Publishing is a separate command rather than the tail of a run: a run can be
interrupted halfway, and there is no point publishing half the results.

---

## Only aggregates leave the perimeter

Shares, counters and identifiers — and nothing else. The invariant is held by
**form** rather than by a list of forbidden words: not one published string
contains a space, because they are all names of models, generators, modes and
profiles, whereas a chunk of the corpus always has spaces in it. The
composition of the dictionary sent is locked down by a test.

```json
{"version": 2, "kind": "answering", "arm": "open_book",
 "score": 0.71, "fabrication_rate": 0.04, "reliable": true, "samples": 515,
 "answerable":   {"samples": 412, "correct": 0.71, "abstain": 0.12,
                  "hallucinate": 0.17, "lmi": 0.19},
 "unanswerable": {"samples": 103, "fabricated": 0.04},
 "discrimination": 0.63, "retrieval": 0.82,
 "models": [{"model": "...", "accuracy": 0.78, "fabrication": 0.02, ...}],
 "skills": [{"generator": "mcq", "samples": 80, "accuracy": 0.9}],
 "trust":  {"judges": 3, "agreement": 0.86, "even_coverage": true,
            "flags": []},
 "dataset":    {"mode": "rolling", "window_days": 7, "cohort": "..."},
 "instrument": {"profile": "default", "judge": "...", "subjects": 9},
 "checked_at": "..."}
```

`version` is mandatory: the receiving side has to know what it is reading, and
a Space that knows only the first version is obliged to refuse rather than to
misunderstand.

Only the direct test (`direct`) goes to the storefront: the numbers of the
`denial_loop` and `monte_carlo` blocks are the owner's internal analytics, and
there is room for one number on an endpoint's card. For the same reason the
verdict of the **first** judge goes to the storefront: a blend of opinions
means nothing.

---

## The kind of product decides which numbers are meaningful

An endpoint in `raw` mode does not formulate an answer — it searches; arm B is
not run against it at all, and there is nothing to measure its "accuracy" from.
Its product is the retrieval hit, and its responsibility is whether the
material it returns nudges someone else's model into invention. An endpoint in
`summary` or `both` mode answers itself and is judged by its answer.

| Kind | Arm | Headline number | Second |
| --- | --- | --- | --- |
| `answering` | B | the accuracy of the answer | inventions on the control half |
| `retrieval` | C | the retrieval hit | inventions on the control half |

So the published arm is not in the settings. It is a property of the node, not
of the installation: in a multi-Space installation one Space is `summary` and
another `raw`, while the setting would be one for both — and the second would
go out to the storefront empty despite excellent retrieval.

**Nine models under test are not folded into an average.** An average over them
would change because we added a tenth to our config, even though nothing
happened to the endpoint. Arm C goes out as a list, named one by one: it is for
the reader to decide what to connect, and the spread answers them directly.

---

## `reliable` is a gate, not an assessment

Four reasons to say "no", and each is its own:

* fewer than thirty questions;
* judge agreement below the threshold;
* uneven coverage across item types;
* some answers without a verdict.

A share that nobody vouches for is worse than no share at all — the reader sees
an absence, but believes an unfounded number.

The reasons go out as **codes**, not as prose: the wording is written by the
storefront, which has its own reader and its own language.

---

## How the card describes itself

`instrument` is needed because the storefront places side by side nodes from
different benchmark installations. Within one installation several Spaces are
measured by one and the same thing — the same judge, the same panel, the same
models under test — and are comparable. Between different installations nothing
is guaranteed, and the storefront has to see that, otherwise it will silently
compare the incomparable.

`dataset` says which set stands behind the number: the mode, the freshness
window, the cohort. A rolling set makes runs on different days non-comparable
line by line — that is not a defect but its point.

**What still cannot be compared even so.** Each Space has its own corpus, and
therefore its own questions, generated out of that same corpus. "71% correct"
and "82% correct" speak about the difficulty of two sets no less than about the
quality of two nodes. What barely depends on the corpus's difficulty is
**inventions on questions without an answer** and **abstention
discrimination**: there no correct answer exists, in an easy corpus or a hard
one. Those are the ones that should be read first.

---

## A refusal from the Space is not a failure

A 404 from the Space means that `benchmarks_mode` is off or the version is old,
and in both cases **the owner has not given consent**. That is a fact, not an
error in the rig, and the benchmark degrades gracefully: the card was already
built before the attempt to hand it over, and a refusal at that last step does
not take it back — it is still on the job (`JobView.card`, see
[control-api.md](control-api.md)), for whoever launched the run to read and, if
they choose, publish afterwards by running again with `publish: true`.

The right of retraction (`retract`) belongs to the owner: the benchmark merely
calls a Space route which itself decides who is allowed.

---

This is the last stage of the pipeline. How all the same things are launched
not from a console but from the Space's UI —
[control-api.md](control-api.md).
