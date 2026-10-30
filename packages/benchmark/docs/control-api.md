# Control from outside

The benchmark can be driven from the command line or from the Space through
the control API. A measurement goes through the same stages as the `cycle`
command ([README.md](README.md#4-the-command-line-cycle)).

The Space's owner decides **what to measure, with what and when**; the
benchmark decides **how the measurement is built**.

```mermaid
sequenceDiagram
    participant U as Owner
    participant S as Syft Space
    participant B as Benchmark
    U->>S: connect the benchmark
    S->>B: GET /capabilities, /schema, /defaults
    B-->>S: what I can do, which fields, which defaults
    U->>S: configure and enable the endpoint
    S->>B: PUT /targets/{key}
    U->>S: "measure now"
    S->>B: POST /targets/{key}/runs
    B-->>S: job queued
    S->>B: GET /targets/{key}/jobs (while it runs)
```

## Three layers of settings

| Layer | What is in it | Where it is set |
| --- | --- | --- |
| **Installation** | defaults under everything: addresses, models, concurrency, thresholds | `installation_settings` row — `PATCH /settings`, `syft-benchmark settings` |
| **Instrument** | arms, blocks, judges, models under test, thresholds | `target.instrument` — per target |
| **Probe** | set mode, window, cap, top-up cost limit (`top_up_max_usd`), generators, `retrieval_top_k`, similarity threshold | `target.probe` — per target |

Applied in that order on every launch (`compose.py`); each layer stores only
overrides, and a `RunRequest` may carry `instrument` / `probe` layers for that
launch only. The full precedence, the environment included, and the
environment-only fields (`BOOTSTRAP_FIELDS`, which `PATCH /settings` refuses):
[01-setup.md](01-setup.md#where-a-setting-lives).

**Secrets** are never in the settings document, snapshots, `/defaults` or
logs, and are never handed out: `GET /credentials` lists names and when each
was set; with no master key, storing one answers 503. How they are stored:
[01-setup.md](01-setup.md#where-a-secret-lives).

## The key and the service

Until `BENCH_CONTROL_TOKEN` is set, the API answers only `/health` and tells
everything else that it is not configured.

```bash
uv run syft-benchmark serve                 # address and port from the settings
uv run syft-benchmark serve --port 8300     # one-off override
```

| Variable | Default | What it does |
| --- | --- | --- |
| `BENCH_CONTROL_TOKEN` | empty | The key; while empty only `/health` answers |
| `BENCH_CONTROL_HOST` | `0.0.0.0` | Listen address |
| `BENCH_CONTROL_PORT` | `8200` | Port |
| `BENCH_CONTROL_ORIGINS` | `[]` | CORS origins; empty means no browser requests |

One process holds the API, the job queue worker and the schedule thread.

### In a container

```bash
cd packages/benchmark
cp .env.example .env                       # at least BENCH_CONTROL_TOKEN
docker compose --profile service up -d --build
```

Without the profile only the database comes up (the command-line flow). The image
runs `alembic upgrade head` and then `serve`; the container runs with `TZ=UTC`.

The Space runs ChromaDB inside its container on `0.0.0.0:8100`; the benchmark
joins the rig's network and reads it at `http://<Space container>:8100`. A
target's `chroma_host` must be the Space's **container name**, not `localhost`.
`docker exec` into the Space's container is the fallback when `chroma_port` is
0 or unreachable; the compose file mounts no docker socket.

| Variable | Default | What it does |
| --- | --- | --- |
| `BENCH_SPACE_NETWORK` | `syft-space-network` | The rig's docker network to join (`docker network ls`) |
| `BENCH_CONTROL_PORT` | `8200` | The host port, bound to 127.0.0.1 only |
| `BENCH_OLLAMA_URL` | `http://host.docker.internal:11434` | A local Ollama on the host; set it in `.env` for an external provider |

The `metrics` extra (torch, for BERTScore) is not in the image; build with
`--build-arg EXTRAS="--extra metrics"` to include it.

## The schedule

A target carries `schedule` — an interval (`24h`, `6h`, `90m`) — and, for a
daily one, `schedule_at` (`HH:MM`, **UTC**). A thread beside the queue checks
the enabled targets every 30 seconds and queues a measurement with
`trigger=schedule`. `next_run_at` on the target says when it fires next.

* A schedule seen for the first time is planned, not fired.
* A changed schedule is replanned.
* Missed windows are not worked off: one overdue measurement, then the plan
  moves forward from now.
* A target already queued or running is not queued twice.

`PUT /targets/{key}` with an enabled schedule is refused (422) when no web
check model (`filter_model`) is set.

## The routes

All routes except `/health` require `BENCH_CONTROL_TOKEN`.

| Route | What it does |
| --- | --- |
| `GET /health` | No key: is the service up, is a key configured |
| `GET /capabilities` | Arms, blocks, generators, models, text metrics, provider |
| `GET /schema` | The shape of the settings fields: names, types, bounds, choices, groups |
| `GET /models` | The model catalogue, filtered (`q`, `vendor`, `supports`, `lacks`, `web_search`, `include_retired`, `limit`) |
| `POST /models/refresh` | Fetch the provider's model list and store it |
| `GET /defaults` | What an unset field resolves to, per layer |
| `GET /settings` | The installation's overrides |
| `PATCH /settings` | Merge some fields into the overrides (JSON Merge Patch): a value sets one, `null` removes it so the default applies, unnamed fields keep theirs. Refuses environment-only fields; answers the whole document |
| `GET /credentials` | Stored secret names and when they were set |
| `PUT/DELETE /credentials/{name}` | Store a secret, sealed; remove one |
| `GET /targets` | All targets, each with its last job |
| `GET/PUT /targets/{key}` | Read, create or replace whole |
| `POST /targets/{key}/check` | Are the index, the node and every configured model reachable |
| `GET /targets/{key}/window?days=` | How many articles the freshness window holds |
| `POST /targets/{key}/runs` | Queue a measurement (202) |
| `POST /targets/{key}/filter` | Queue a filter pass over pending pairs (202) |
| `POST /targets/{key}/judge` | Queue a judging pass over pending verdicts (202) |
| `POST /targets/{key}/session` | Mint a session token for the `/console/*` routes — see [The console](#the-console) |
| `GET /targets/{key}/jobs` | The target's last 20 jobs |
| `POST /jobs/{id}/cancel` | Ask a queued or running job to stop |

Launches on a disabled target answer 409. `PUT /targets/{key}` and
`POST /targets/{key}/runs` answer 422 when a judge and a tested model share a
vendor under `judge_policy=strict`; a run that evaluates also needs
`filter_model` (422 "Choose a web check model").

Reasons (why an arm is unmeasurable, why a job did not finish, `trust.flags`)
are codes; the UI words them. The text of a failed call passes through as is.

### `/schema` and `/models`

`/schema` sends the shape of the fields, not labels, so a new setting needs no
change in the Space. Model fields say `catalog: "models"`; the form fetches the
list from `/models`.

* One identifier per model, whoever serves it (`anthropic/claude-sonnet-5`);
  the provider's own name is resolved at call time.
* A moving alias (`~anthropic/claude-sonnet-latest`) is pinned to its current
  model when a setting is saved; the catalogue hands out the map as `pins`.
* The catalogue is not a whitelist: an unknown model is accepted and marked
  unknown.
* The shipped `data/models.json` is the floor; `POST /models/refresh` stores a
  newer list in `model_catalog`. Refreshing is a call outside the perimeter: it
  answers 403 naming the host when the perimeter forbids it.
* When `ollama_url` points at an Ollama, its pulled models are listed first.

## The console

The `/console/*` routes serve one target and take a session token, not the
installation key: `POST /targets/{key}/session` (installation key required)
mints a signed token scoped to one target, valid for an hour
(`control/session.py`; no table). The Space mints one per request and proxies
the `/console/*` calls through it.

`/console/*` returns what the service routes never do: question and answer
texts, reasoning, block details (`denial`, `repeats` from `Result.extra`).

| Route | What it does |
| --- | --- |
| `GET/PUT /console/probe` | This target's probe layer, its fields, the inherited values. The instrument is not editable here |
| `GET /console/pairs` | This target's pairs, filterable by status, cohort, generator, job |
| `PATCH/DELETE /console/pairs/{id}` | Override a pair's status; delete it if no result references it |
| `GET /console/results` | This target's results, filterable by verdict, pair (`qa_id`), `model`, job; `prompts` adds the audit trail. With `job`, `counted` marks the row the job's figures count for each answer (`counted.pick`) |
| `POST/DELETE /console/results/{id}/verdict` | Record a verdict by hand (inserted, not a rewrite); withdraw it |
| `POST /console/runs` / `filter` / `judge` | The same launches as the service routes |
| `GET /console/jobs` | This target's job history |

Run reports, under `/console/report`:

| Route | What it does |
| --- | --- |
| `GET /runs` | Active jobs and a page of finished runs (`from`, `to`, `limit`, `offset`) |
| `GET /runs/{job}` | One run's report, without per-question rows |
| `DELETE /runs/{job}` | Delete a finished run: its runs, answers, verdicts, overrides, cached figures, writer calls and its records on the questions. Questions stay. 409 while queued or running |
| `GET /runs/{job}/generated` | The questions the job wrote (`generator`, `status`), and its build per kind (`topped_up`: written by the top-up) |
| `GET /runs/{job}/writing` | The job's writer calls that dropped drafts or failed, one item per call and kind |
| `GET /runs/{job}/pairs?ids=` | Questions of the target by id (comma-separated, at most 200), whichever job wrote them |
| `GET /runs/{job}/pairs/{qa}` | One question of the target with its meta |
| `GET /runs/{job}/filter` | The job's filter decisions, including on questions earlier jobs wrote (`generator`, `stage`, `outcome`), paged; `limit=0` with a `generator` returns all of that kind; `counts` are of the `generator`, before `stage` and `outcome` |
| `GET /runs/{job}/questions` | One model's questions in the run, paged |
| `GET /runs/{job}/questions/{qa}` | One question in full |
| `GET /runs/{job}/questions/{qa}/fragments` | The passages sent with the arm C answer |
| `GET /runs/{job}/summary.docx` | The run's summary document: figures only |
| `GET /runs/{job}/export.xlsx` | Everything in the run, full texts: sheets Run, Generated, Rejected, Kept, Writer calls (the writer-call log: dropped drafts, failed calls), Filter, Answers, Judging, Timing |

The pairs of `/generated`, `/pairs` and `/pairs/{qa}` carry `writer_call` and
`entity_call` (`RecordedCall`): the call's texts, `user` with the passage in
place, read from whichever pair of the call stores them, else from the
writer-call log (`report/pair_calls.py`).

## The model provider

`/capabilities` describes the provider without the key: address, app name,
whether a key is set, open external hosts, and per role (generator, subject,
judge, filter — the web check) its address, whether a key is set, whether
it has its own provider, and `local`: whether the address stays inside the
perimeter (`config.host_is_inside`), which the Space shows as "on this machine".
The key is changed in the benchmark's settings or secrets, never through the
Space.

## Jobs

A launch queues a job and answers `202`; a worker thread runs it. One active
job per target: launching while one is queued or running returns that job.

| State | Meaning |
| --- | --- |
| `queued` | Waiting |
| `running` | In progress; `phase` (`generate`, `filter`, `evaluate`, `judge`) says where |
| `succeeded` | Finished; a non-empty `error` means partly |
| `failed` | Did not reach the end |
| `cancelled` | Stopped; what was measured stays |

`kind` is `pipeline` (`/runs`), `filter` or `judge`. Stopping is a request:
the run finishes the current question and exits. A job whose priced calls reach
`max_job_usd` (instrument layer; default 100, 0 — no cap) is stopped the same
way and ends `cancelled` with `over_budget: …`.

Every run a job opens carries its id, so a launch's report and audit can be
read afterwards (`syft-benchmark audit <space> --job <id>`). A launch that
resumed a finished pass opens no run for it; those verdicts belong to the
earlier launch. Verdicts added after a launch (a judging pass, judging through
a chat, an override) are recorded under the launch whose answers they grade.
Runs started from the CLI have no job.

| Error code | When |
| --- | --- |
| `nothing_generated: …` | The set was to be built and every generator call failed |
| `no_questions` | There was nothing to ask |
| `nothing_graded: …` | Questions were asked, no verdict came out |
| `over_budget: …` | The spending cap stopped the job |
| `target_gone` | The target was deleted |
| `service_restarted` | The process restarted mid-job |

### What a launch does

`RunRequest` fields:

| Field | Meaning |
| --- | --- |
| `generate` | Build the set first. `null` — as `generate_in_cycle` says |
| `filter` | Screen the pending pairs just built. `null` — follow `generate` |
| `evaluate` | Ask and grade. `null` — yes |
| `defer_judging` | Collect answers without a judge, leaving verdicts `pending`. Default `false` |
| `limit` | Items **per generator**, for a trial run |
| `instrument`, `probe` | Layers for this launch only |

`evaluate: false` only refreshes the set: no questions, `total` stays
`0`. `defer_judging: true` leaves grading to `POST /targets/{key}/judge`.

## The target registry

Targets live in the `targets` table. `config/spaces.json` is a seed: a target
missing from the table is taken from the file at start-up. Changes from the UI
are never written back to the file. A target stores overrides only.

`POST /targets/{key}/check` walks three roads: to the index (HTTP or
`docker exec`), to the node (HTTP with the token), and to each configured model
(one request per distinct address and name). It returns the collections
actually present in the index: the collection is named after the Space's
dataset, not the target key, and is a field of the target.
