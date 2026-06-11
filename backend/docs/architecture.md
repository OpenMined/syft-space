# Architecture

Syft Space is a full-stack application: a **Vue 3 SPA** talking to a **FastAPI
backend** that orchestrates vector databases, LLMs, payments, and an optional
connection to the **SyftHub** marketplace. This document covers the backend's
shape and runtime behavior. For the domain model see [Core
Concepts](./concepts.md); for the request path see [Query Flow](./query-flow.md).

## System overview

```mermaid
flowchart TB
    subgraph client["Clients"]
        FE["Vue 3 SPA<br/>(dashboard)"]
        EXT["External users<br/>(via SyftHub)"]
    end

    subgraph backend["FastAPI Backend"]
        MW["Middleware<br/>CORS → Tenant → AdminKey"]
        subgraph resources["Resource APIs"]
            DS["Datasets"]
            MD["Models"]
            EP["Endpoints"]
            PO["Policies"]
            WA["Wallets"]
            PA["Payments"]
            AN["Analytics"]
            MK["Marketplaces"]
        end
        subgraph svc["Lifecycle services"]
            PX["ProxyService → ngrok tunnel"]
            PV["ProvisionerManager"]
            IN["IngestionManager + file watcher"]
            HB["HeartbeatManager"]
        end
        DB[("SQLite<br/>app.db + analytics.db")]
    end

    subgraph ext["External services"]
        CH["ChromaDB<br/>(local subprocess)"]
        WV["Weaviate<br/>(remote)"]
        LLM["OpenAI-compatible LLM"]
        TEMPO["Tempo blockchain<br/>(MPP crypto payments)"]
        GW["Stripe / Xendit"]
        HUB["SyftHub marketplace"]
    end

    FE -->|REST /api/v1| MW
    EXT -->|query via tunnel| PX
    MW --> resources
    resources --> DB
    svc --> DB
    DS --> CH & WV
    MD --> LLM
    PA --> TEMPO & GW
    PX <--> HUB
    HB --> HUB
```

## Component map

Every component lives under `syft_space/components/` and follows the same
internal layout (see [Component pattern](#component-pattern)).

| Component | Responsibility |
| --- | --- |
| `datasets` | CRUD for datasets + provisioner lifecycle management |
| `dataset_types` | Registry of dataset-type **bindings** (source × vector store) |
| `sources` | Where data comes from — file pickers + ingestion (`local_file`, `noop`) |
| `vector_stores` | Where data is indexed/searched (`chromadb_local`, `weaviate_remote`) |
| `ingestion` | File-watch + batch ingestion jobs into vector stores |
| `models` | CRUD for LLM instances |
| `model_types` | Registry of model types (`openai`) |
| `endpoints` | Endpoint CRUD, the **query pipeline**, and marketplace publishing |
| `policies` | Policy CRUD + capability validation |
| `policy_types` | Policy implementations — access, rate limit, PII filter, payments |
| `wallets` | Payment **credential** storage (mpp / stripe / xendit) |
| `payments` | The **money** — invoices, ledger, balances, MPP balance queries, webhooks |
| `marketplaces` | SyftHub account credentials, registration, publishing |
| `analytics` | Query-event capture + dashboard stats (separate DB) |
| `feedback` | In-app bug reports / feedback → forwarded to SyftHub |
| `settings` | Public URL + ngrok proxy config + diagnostics toggle |
| `tenants` | Multi-tenancy entities + request-scoping middleware |
| `auth` | Admin-key middleware, bearer scheme, `@public_route` marker |
| `shared` | Database, logging, async utils, lifecycle protocol, SyftHub client, proxy |

### The source / vector-store split

The big architectural idea in the data layer: **a dataset type is a binding of
a *source* to a *vector store*.** The two axes are orthogonal.

```mermaid
flowchart LR
    subgraph sources["Sources — where data comes from"]
        LF["local_file"]
        NO["noop<br/>(ingested externally)"]
    end
    subgraph stores["Vector stores — where it's indexed"]
        CL["chromadb_local"]
        WR["weaviate_remote"]
    end
    subgraph bindings["Dataset types (bindings)"]
        B1["local_file<br/>= local_file × chromadb_local"]
        B2["remote_weaviate<br/>= noop × weaviate_remote"]
    end
    LF --> B1
    CL --> B1
    NO --> B2
    WR --> B2
```

This means new combinations (e.g. *S3 files → Weaviate*, *local files →
Qdrant*) are a small binding, not a new monolithic type. See
[Extending the Platform](./extending.md).

## Component pattern

Each component is a self-contained vertical slice:

```
component/
├── entities.py     # SQLModel database models
├── repository.py   # Data access (CRUD), one DB session per operation
├── handlers.py     # Business logic (the "use cases")
├── schemas.py      # Pydantic request/response models
├── routes.py       # build_*_routes(...) → an APIRouter
└── __init__.py
```

Wiring happens once, explicitly, in [`main.py`](../syft_space/main.py):
repositories → handlers → `build_*_routes()` → mounted under `/api/v1`. There
are **no import side effects** — registries and routes are populated by explicit
function calls, which keeps startup fast and dependencies obvious.

## Startup & lifecycle

`main.py` defines an async `lifespan` that runs this sequence on boot:

```mermaid
flowchart TB
    A["Init Sentry (diagnostics-gated)"] --> B["Run migrations<br/>app.db + analytics.db"]
    B --> C["Create default tenant +<br/>load settings from config"]
    C --> D["Start lifecycle services<br/>(ordered)"]
    D --> E["Fire-and-forget syncs<br/>(after proxy ready)"]
    E --> F["▶ App serves requests"]
    F --> G["Shutdown services<br/>(reverse order)"]
    G --> H["Drain analytics tasks<br/>+ dispose DB engines"]
```

**Lifecycle services** implement a shared `LifecycleService` protocol and start
in this order (shutdown is the reverse):

1. **ProxyService** — opens the ngrok tunnel, fetching credentials from SyftHub.
2. **ProvisionerManager** — starts/stops vector-store provisioners (e.g. the
   ChromaDB subprocess) and re-discovers them after restart from persisted state.
3. **LocalFileWatcher** — owns the shared filesystem observer.
4. **IngestionManager** — the background worker that ingests watched files
   (waits for provisioners to be ready via a coordination event).
5. **EndpointHeartbeatManager** — periodically reports published-endpoint health
   to marketplaces.

After services start, two **fire-and-forget** tasks run once the proxy is ready:
sync the public URL to the marketplace, and bulk-sync published endpoints.
Dataset-type imports are also warmed in the background to avoid first-request
latency. None of these block startup — failures are logged and the server
continues.

## External integration: SyftHub

The backend talks to SyftHub (the marketplace) through a single
`SyftHubClient` (httpx). Two directions:

```mermaid
sequenceDiagram
    participant SS as Syft Space
    participant HUB as SyftHub
    participant U as External user

    Note over SS,HUB: Outbound (Syft Space → SyftHub)
    SS->>HUB: login (marketplace credentials)
    SS->>HUB: publish / unpublish endpoints
    SS->>HUB: bulk endpoint + public-URL sync (on boot)
    SS->>HUB: periodic health heartbeat
    SS->>HUB: fetch ngrok tunnel credentials

    Note over U,SS: Inbound (user → Syft Space, via tunnel)
    U->>HUB: discover endpoint
    U->>SS: POST /endpoints/{slug}/query (+ SyftHub token)
    SS->>HUB: verify token
    SS-->>U: raw / summary / both
```

The tunnel makes a locally-running Syft Space reachable from the public internet
without exposing the host directly. See [Query Flow](./query-flow.md) for what
happens inside that inbound query.

## Technology stack

| Layer | Choice |
| --- | --- |
| **Web framework** | FastAPI (async) on Uvicorn (ASGI) |
| **Language** | Python 3.12 |
| **ORM / models** | SQLModel + SQLAlchemy, Pydantic v2 |
| **Database** | SQLite via `aiosqlite` (main + analytics), Alembic migrations |
| **HTTP client** | httpx (async) |
| **Vector DB (local)** | ChromaDB (subprocess) |
| **Vector DB (remote)** | Weaviate |
| **LLM** | OpenAI SDK — any OpenAI-compatible API (OpenAI, vLLM, Ollama) |
| **Doc processing** | Docling (PDF, DOCX, …) |
| **File watching** | watchdog |
| **Payments (crypto)** | `mpp` + Web3 on the Tempo blockchain |
| **Payments (gateway)** | Stripe, Xendit |
| **Tunnel** | ngrok |
| **Logging / errors** | loguru + Sentry (diagnostics-gated) |
| **Analytics** | self-hosted event store (separate SQLite DB) |
| **Tooling** | uv, Ruff (format + lint), mypy, pytest |

The frontend is Vue 3 + TypeScript + Pinia + shadcn/vue + Tailwind, built with
Vite/Bun and served as static files by the backend under `/frontend`.
</content>
