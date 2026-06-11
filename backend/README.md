# Syft Space Backend

A FastAPI **RAG platform** for creating, protecting, and publishing AI-powered
endpoints backed by vector databases and language models. You connect
**datasets** and **models**, combine them into **endpoints**, guard them with
**policies** (access, rate limits, payments), and **publish** them to the
SyftHub marketplace — all while your raw data stays under your control.

## Documentation

Full docs live in **[`docs/`](./docs/)**:

| Doc | What it covers |
| --- | --- |
| [Getting Started](./docs/getting-started.md) | Install, run, and build your first endpoint |
| [Architecture](./docs/architecture.md) | System design, components, startup lifecycle, tech stack |
| [Core Concepts](./docs/concepts.md) | Sources, vector stores, datasets, models, endpoints, policies, wallets |
| [API Overview](./docs/api-overview.md) | Auth, conventions, resource map (live reference at `/docs`) |
| [Query Flow](./docs/query-flow.md) | What happens during an endpoint query |
| [Payments & Wallets](./docs/payments.md) | Charging for queries (MPP crypto + Stripe/Xendit) |
| [Extending](./docs/extending.md) | Add a source, vector store, model, or policy type |
| [Configuration](./docs/configuration.md) | Env vars, auth, multi-tenancy, Docker |
| [Migrations](./docs/migrations.md) | Database schema migrations |

## Quick start

```bash
# Install (Python 3.12+, uv recommended)
uv venv -p 3.12
uv pip install -e ".[dev]"

# Run (dev mode — no auth)
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port 8080
```

Then open **<http://localhost:8080/docs>** for the interactive API, or follow
the [Getting Started](./docs/getting-started.md) tutorial.

## Project layout

```
backend/syft_space/
├── main.py                 # App entry point — wires repositories → handlers → routes
├── config.py               # Environment configuration
├── alembic/                # Main DB migrations  (alembic_analytics/ for analytics DB)
└── components/             # One vertical slice per feature
    ├── datasets/  dataset_types/  sources/  vector_stores/  ingestion/
    ├── models/  model_types/
    ├── endpoints/  policies/  policy_types/
    ├── wallets/  payments/  marketplaces/
    ├── analytics/  feedback/  settings/  tenants/  auth/
    └── shared/             # Database, logging, lifecycle, SyftHub client, proxy
```

Each component follows the same pattern: `entities` (SQLModel) → `repository`
(CRUD) → `handlers` (business logic) → `schemas` (Pydantic) → `routes`. See
[Architecture › Component pattern](./docs/architecture.md#component-pattern).

## Development

Run from `backend/`:

```bash
uv run --extra lint ruff format .   # format
uv run --extra lint ruff check .    # lint
mypy .                              # type-check
pytest                              # tests
```

See [Configuration](./docs/configuration.md) for the full command and env-var
reference.

## License

Apache 2.0 · [github.com/OpenMined/syft-space](https://github.com/OpenMined/syft-space)
</content>
