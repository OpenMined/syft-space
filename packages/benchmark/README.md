# syft-benchmark

An honesty benchmark for [Syft Space](https://github.com/OpenMined/syft-space) endpoints.

It builds a question set from a Space's corpus, asks it three ways, and hands
the Space a card to publish. What is under test is **the model's interaction
with RAG**:

| Arm | Who answers | What it gets | Correct behaviour | What it measures |
| --- | --- | --- | --- | --- |
| **A** `closed_book` | the model under test | the question only | abstain | the model's honesty |
| **B** `open_book` | the endpoint | the question; it has the corpus | a correct answer | the owner's product |
| **C** `model_with_context` | the **same** model as in A | question + the endpoint's retrieval | a correct answer | the model's work with RAG |

Half of the set is answerable from the corpus; the control half has no answer,
and the correct behaviour there is to abstain or refute the premise. Outcomes:
`correct`, `abstain`, `hallucinate` (an explanation can also be `incomplete`).

**The benchmark measures, the Space publishes, SyftHub displays.** There are no
hub credentials here.

Documentation: [docs/README.md](docs/README.md).

---

## Running it as a service

The control API, the job queue and the schedule run in one container, driven
from the Space's UI. The container joins the rig's docker network and reads the
Space's ChromaDB (port 8100 inside the Space's container) over HTTP.

```bash
cd packages/benchmark

cp .env.example .env    # BENCH_CONTROL_TOKEN, or only /health answers
uv run syft-benchmark secrets keygen >> .env   # the master key for stored secrets
docker compose --profile service up -d --build
```

The schema is migrated on start. Connect the benchmark from the Space's UI and
configure a target there; its `chroma_host` is the Space's **container name**
(inside a container `localhost` is the benchmark itself).

`BENCH_SPACE_NETWORK` names the network to join when it is not
`syft-space-network` (`docker network ls`). Details: [control-api](docs/control-api.md).

---

## Quick start from the console

Run from this directory: `alembic.ini` paths are relative to it, and the
virtualenv is its own.

```bash
cd packages/benchmark

cp .env.example .env
cp config/spaces.example.json config/spaces.json   # fill in your own Spaces

docker compose up -d          # Postgres on 5442, without the service
uv sync
uv run alembic upgrade head

uv run syft-benchmark doctor
uv run syft-benchmark chunks docs --collection syft_knowledge_base

uv run syft-benchmark generate docs --limit 2   # 2 items from EVERY generator
uv run syft-benchmark filter docs
uv run syft-benchmark freeze docs --out config/slice-docs.json --limit 60
uv run syft-benchmark evaluate docs            # the arms from the settings
uv run syft-benchmark status docs
uv run syft-benchmark report docs --out reports/latest.md
uv run syft-benchmark report docs --docx reports/latest.docx   # with charts
uv run syft-benchmark audit docs --out reports/audit.jsonl
uv run syft-benchmark publish docs
```

Start with `--limit 2`: it exercises every kind of item cheaply.

---

## Commands

| Command | Stage | In detail |
| --- | --- | --- |
| `spaces` | the Space registry and the current settings | [01-setup](docs/01-setup.md) |
| `doctor` | check that everything a run depends on is in place | [01-setup](docs/01-setup.md) |
| `chunks <space>` | read the Space's index and show how much material there is | [01-setup](docs/01-setup.md) |
| `models [query]` | the model catalogue; `--refresh` fetches the provider's list | [01-setup](docs/01-setup.md) |
| `settings` | the installation's settings row: `show`, `set`, `unset` | [01-setup](docs/01-setup.md) |
| `secrets` | provider keys and Space tokens, sealed: `keygen`, `list`, `set`, `unset`, `rotate` | [01-setup](docs/01-setup.md) |
| `generators` | the generators: what each builds and how it is judged | [02-generation](docs/02-generation.md) |
| `generate` | build items; `--mode`, `--period`, `--new-cohort`, `--limit` | [02](docs/02-generation.md), [03](docs/03-dataset.md) |
| `filter` | screen `pending` pairs into `active` / `rejected` | [02-generation](docs/02-generation.md) |
| `freeze <space> --out <file>` | freeze a slice of questions | [03-dataset](docs/03-dataset.md) |
| `cohorts <space>` | the set's cohorts and the comparison between them | [03-dataset](docs/03-dataset.md) |
| `evaluate -m <arm> -b <block>` | ask the questions and judge the answers; `--defer-judging` | [04-evaluation](docs/04-evaluation.md) |
| `status` | what is collected, what is missing, what will finish it | [04-evaluation](docs/04-evaluation.md) |
| `upstreams` | which host served each call, and how the verdicts fell | [04-evaluation](docs/04-evaluation.md) |
| `export-questions` / `import-answers` | testing a model by hand through a chat | [04-evaluation](docs/04-evaluation.md) |
| `judge` | grade the answers a deferred pass left `pending` | [05-judging](docs/05-judging.md) |
| `export-judging` / `import-judging` | judging through a chat, without an API | [05-judging](docs/05-judging.md) |
| `report` | metrics; `--docx` writes a document with charts | [06-report](docs/06-report.md) |
| `audit <space>` | export the raw records; `--job`, `--judge`, `--no-context` | [07-audit](docs/07-audit.md) |
| `publish` / `retract <space>` | hand the card to the Space; retract it | [08-publish](docs/08-publish.md) |
| `cycle [--every 24h --at 03:00]` | the whole cycle from the console | [docs/README](docs/README.md) |
| `serve` | the control API, the queue and the schedule | [control-api](docs/control-api.md) |

Commands that take `[space]...` run over every registered Space when none is
given. Publishing is a separate command: an interrupted run must not publish
half its results. With the service up, leave scheduling to it and use `cycle`
only for a single pass.

---

## Running the tests

```bash
uv run pytest
```

`tests/conftest.py` never uses the configured database: it redirects
`BENCH_DATABASE_URL` to a sibling database with `_tests` appended, creating and
migrating it if missing (some tests clear the settings row and every stored
credential). `BENCH_TEST_DATABASE_URL` overrides it. Without a database server
the tests that need one skip with a warning.
