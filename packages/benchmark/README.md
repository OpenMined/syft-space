# syft-benchmark

An honesty benchmark for [Syft Space](https://github.com/OpenMined/syft-space) endpoints.

It builds a dataset from a Space's corpus, tests the model, the endpoint and the
pair of them across three arms, and hands the Space a verdict to publish.

What is under test is not the RAG system by itself but **the model's interaction
with it**: first the model answers alone, then the endpoint answers, then the
same model is handed the material the endpoint retrieved and answers with it.

| Arm | Who answers | What it gets | Correct behaviour | What it measures |
| --- | --- | --- | --- | --- |
| **A** `closed_book` | the model under test | the question only | abstain | the model's honesty |
| **B** `open_book` | the endpoint | the question; it has the corpus | a correct answer | the owner's product |
| **C** `model_with_context` | the **same** model as in A | question + the endpoint's retrieval | a correct answer | the model's work with RAG |

The set has two halves: on one, an answer exists in the corpus by construction;
on the other there is no answer at all — and the correct behaviour there is to
stay silent. There are three outcomes: `correct`, `abstain`, `hallucinate`.

**The benchmark measures, the Space publishes, SyftHub displays.** There are no
hub credentials here and there must not be: metrics go to the Space, and the
Space puts them out under its own account — exactly as it already does with
health.

**Documentation — [docs/README.md](docs/README.md):** the problem, the pipeline,
the stages, and links to everything else.

---

## Running it as a service

The benchmark is a service: the control API, the job queue and the schedule in
one container, driven from the Space's UI. It joins the rig's docker network
and reads the Space's index over HTTP — the Space keeps ChromaDB inside its own
container on port 8100, and a sibling container reaches it by name.

```bash
cd packages/benchmark

cp .env.example .env    # BENCH_CONTROL_TOKEN, or only /health answers
uv run syft-benchmark secrets keygen >> .env   # the master key for stored secrets
docker compose --profile service up -d --build
```

The schema is brought up to date on start. Then connect it from the Space's UI
and configure a target there — with one thing that cannot be guessed: its
`chroma_host` is the Space's **container name**. Inside a container `localhost`
is the benchmark itself.

`BENCH_SPACE_NETWORK` names the network to join when the rig does not call it
`syft-space-network` — `docker network ls` says which. The rest is in
[control-api](docs/control-api.md).

---

## Quick start from the console

The console is where the pipeline is developed and a measurement is taken
apart by hand — stage by stage, with the files in view. Everything below runs
from this directory: the config paths and `prepend_sys_path` in `alembic.ini`
are relative to it, and the virtualenv is its own — the benchmark shares the
repository with the Space, not a process.

```bash
cd packages/benchmark

cp .env.example .env
cp config/spaces.example.json config/spaces.json   # fill in your own Spaces

docker compose up -d          # the benchmark's Postgres on 5442, without the service
uv sync
uv run alembic upgrade head   # schema

uv run syft-benchmark doctor  # is everything in place
uv run syft-benchmark chunks docs --collection syft_knowledge_base

uv run syft-benchmark generate docs --limit 2   # 2 items from EVERY generator
uv run syft-benchmark freeze docs --out config/slice-docs.json --limit 60
uv run syft-benchmark evaluate docs            # all three arms from the settings
uv run syft-benchmark status docs              # what is collected, what is left
uv run syft-benchmark report docs --out reports/latest.md
uv run syft-benchmark report docs --docx reports/latest.docx   # with charts
uv run syft-benchmark audit docs --out reports/audit.jsonl
uv run syft-benchmark publish docs
```

Start with `--limit 2`: that is enough to see a working pipeline across every
kind of item, and cheap if it does not work.

---

## Commands

| Command | Stage | In detail |
| --- | --- | --- |
| `spaces` | the Space registry and its settings | [01-setup](docs/01-setup.md) |
| `doctor` | check that everything a run depends on is in place | [01-setup](docs/01-setup.md) |
| `chunks <space>` | read the Space's index and show how much material there is | [01-setup](docs/01-setup.md) |
| `models [query]` | the model catalogue; `--refresh` fetches the provider's list afresh | [01-setup](docs/01-setup.md) |
| `upstreams` | which host actually served each answer, and how the verdicts fell | [04-evaluation](docs/04-evaluation.md) |
| `generators` | the generator line-up, model roles, blocks and their settings | [02-generation](docs/02-generation.md) |
| `generate` | build items; `--mode`, `--period`, `--new-cohort` pick the set | [02](docs/02-generation.md), [03](docs/03-dataset.md) |
| `freeze <space> --out <file>` | freeze a slice of questions | [03-dataset](docs/03-dataset.md) |
| `cohorts <space>` | the set's cohorts and the comparison between them | [03-dataset](docs/03-dataset.md) |
| `evaluate -m <arm> -b <block>` | ask the questions and judge the answers | [04-evaluation](docs/04-evaluation.md) |
| `status` | what is collected, what is missing, and what will finish it | [04-evaluation](docs/04-evaluation.md) |
| `export-questions` / `import-answers` | testing a model by hand through a chat | [04-evaluation](docs/04-evaluation.md) |
| `export-judging` / `import-judging` | judging through a chat, without an API | [05-judging](docs/05-judging.md) |
| `report` | fold verdicts into metrics; `--docx` — a document with charts | [06-report](docs/06-report.md) |
| `audit <space>` | export the raw records; `--job` — of one launch | [07-audit](docs/07-audit.md) |
| `publish` / `retract <space>` | hand the metrics to the Space; retract what was published | [08-publish](docs/08-publish.md) |
| `cycle --every 24h --at 03:00` | the whole daily cycle, from the console | [docs/README](docs/README.md) |
| `settings` | the installation's own defaults: `show`, `set`, `unset` | [01-setup](docs/01-setup.md) |
| `secrets` | the provider keys, sealed: `keygen`, `list`, `set`, `unset`, `rotate` | [01-setup](docs/01-setup.md) |
| `serve` | the service: the control API, the queue and the schedule | [control-api](docs/control-api.md) |

Publishing is a separate command rather than the tail of a run: a run can be
interrupted halfway, and there is no point publishing half the results.

`serve` raises the same thing for people who do not live in a console: the
Space's owner connects the benchmark on their side, configures it and presses
"measure" — or sets a schedule and presses nothing. A key is mandatory,
otherwise the API answers only on `/health`: its one working route costs hours
and money.

`cycle` is the console's way to the same place and is not the deployment: the
service fires its own schedule, and a `cycle` running beside it would be a
second source of truth measuring the same nodes.

---

## State

The three-arm pipeline, the control half of the set, the audit log, option
shuffling, the report as a document, parallel runs, resuming from the point of
interruption, the frozen slice, the rolling set, cohort rebuilds, judging
without an API, the control API, the schedule the service fires itself, a
measurement readable back by the launch that made it, and the settings and the
sealed secrets in the database rather than in a file on somebody's host — all
in the code. 481 tests pass, `mypy --strict` is clean, `ruff` is clean over `src` and `tests`.

---

## Running the tests

```bash
uv run pytest
```

The tests choose their own database and cannot be handed a live one. Several of
them clear the settings row and every stored credential — that is what they are
for — so `tests/conftest.py` redirects `BENCH_DATABASE_URL` to a sibling
database named after it with `_tests` on the end, creating and migrating it if
it is not there. Pointed at a running installation, those tests would unseal the
provider key, drop the methodology row and leave the service calling a local
Ollama for models named at a gateway.

`BENCH_TEST_DATABASE_URL` overrides the derivation for a CI that makes its own
database. With no server at all the tests that need one skip themselves, with a
warning saying so.
