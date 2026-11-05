# syft-benchmark

An honesty benchmark for [Syft Space](https://github.com/OpenMined/syft-space) endpoints.

It builds a question set from a Space's corpus, asks it with and without the
endpoint's retrieval (arms A and C, [04-evaluation](docs/04-evaluation.md#the-arms))
and grades the answers as `correct`, `abstain` or `hallucinate`
([05-judging](docs/05-judging.md)); the Space shows the results.

Results stay inside the Space; there are no SyftHub credentials here
([privacy](docs/privacy.md#4-there-are-no-syfthub-credentials-here)).

Documentation: [docs/README.md](docs/README.md).

---

## Running it as a service

```bash
cd packages/benchmark
docker compose --profile service up -d --build
```

The control API, the job queue and the schedule in one container, driven from
the Space. Setup, ports and the docker network:
[control-api](docs/control-api.md#in-a-container).

---

## Quick start from the command line

Every command runs from this directory: `alembic.ini` (`prepend_sys_path`)
and the `config/` paths are relative to it, and the virtualenv is its own.

```bash
cd packages/benchmark

cp .env.example .env
cp config/spaces.example.json config/spaces.json   # fill in your own Spaces

docker compose up -d          # Postgres on 5442, without the service
uv sync
uv run alembic upgrade head

uv run syft-benchmark doctor
uv run syft-benchmark chunks docs --collection syft_knowledge_base

uv run syft-benchmark generate docs --limit 2   # a small budget for every kind
uv run syft-benchmark filter docs
uv run syft-benchmark freeze docs --out config/slice-docs.json --limit 60
uv run syft-benchmark evaluate docs            # the arms from the settings
uv run syft-benchmark status docs
uv run syft-benchmark report docs --out reports/latest.md
uv run syft-benchmark report docs --docx reports/latest.docx   # with charts
uv run syft-benchmark audit docs --out reports/audit.jsonl
```

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
| `generators` | the generator line-up, model roles, blocks and effective settings | [01-setup](docs/01-setup.md) |
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
| `cycle [--every 24h --at 03:00]` | the whole cycle from the command line | [docs/README](docs/README.md#4-the-command-line-cycle) |
| `serve` | the control API, the queue and the schedule | [control-api](docs/control-api.md) |

Commands that take `[space]...` run over every registered Space when none is
given.

---

## Running the tests

```bash
uv run pytest
```

`tests/conftest.py` never uses the configured database: it redirects
`BENCH_DATABASE_URL` to a sibling database with `_tests` appended, creating and
migrating it if missing. `BENCH_TEST_DATABASE_URL` overrides it. Without a
database server the tests that need one skip with a warning.
