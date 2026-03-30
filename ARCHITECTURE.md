# Syft Space Architecture

## High-Level Architectural Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SYFT SPACE                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                     Vue 3 Frontend (SPA)                            │     │
│  │                                                                     │     │
│  │  Pages: Home │ Datasets │ Models │ Endpoints │ Settings │ Analytics │     │
│  │  State: Pinia Stores    │  UI: shadcn/vue + Tailwind               │     │
│  │  API Client: Axios → /api/v1/*                                      │     │
│  └────────────────────────────┬────────────────────────────────────────┘     │
│                               │ REST API                                     │
│  ┌────────────────────────────▼────────────────────────────────────────┐     │
│  │                    FastAPI Backend                                  │     │
│  │                                                                     │     │
│  │  Middleware: Auth (AdminKey) → Tenant → CORS                        │     │
│  │                                                                     │     │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐               │     │
│  │  │ Datasets │ │  Models  │ │ Endpoints │ │ Policies │               │     │
│  │  │          │ │          │ │           │ │          │               │     │
│  │  │ ChromaDB │ │ OpenAI-  │ │ Query     │ │ Rate     │               │     │
│  │  │ Weaviate │ │ compat   │ │ Publish   │ │ Limit    │               │     │
│  │  │          │ │ API      │ │ Unpublish │ │ Access   │               │     │
│  │  └────┬─────┘ └────┬─────┘ └─────┬─────┘ │ Account  │               │     │
│  │       │             │             │        └────┬─────┘             │     │
│  │       │             └──────┬──────┘             │                   │     │
│  │       │                    │                    │                   │     │
│  │       │         ┌──────────▼──────────┐         │                   │     │
│  │       │         │   Endpoint Query    │◄────────┘                   │     │
│  │       │         │  Dataset.search()   │                             │     │
│  │       │         │  Model.chat()       │                             │     │
│  │       │         │  Policy.enforce()   │                             │     │
│  │       │         └────────────────────-┘                             │     │
│  │       │                                                             │     │
│  │  ┌────▼──────────────────────────────────────────────────────┐      │     │
│  │  │              Lifecycle Services                            │     │     │
│  │  │                                                            │     │     │
│  │  │  ProxyService ──────► ngrok tunnel ──► public URL          │     │     │
│  │  │  ProvisionerManager ► start/stop dataset backends          │     │     │
│  │  │  IngestionManager ──► watchdog file monitoring → ingest    │     │     │
│  │  │  HeartbeatManager ──► periodic endpoint health reporting   │     │     │
│  │  └────────────────────────────────────────────────────────────┘     │     │
│  │                                                                     │     │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐              │     │
│  │  │  Tenants    │  │  Settings    │  │  Marketplaces │              │     │
│  │  │  (multi-    │  │  (public URL,│  │  (credentials,│              │     │
│  │  │   tenancy)  │  │   config)    │  │   sync state) │              │     │
│  │  └─────────────┘  └──────────────┘  └───────┬───────┘              │     │
│  │                                              │                     │     │
│  │  ┌───────────────────────────────────────────▼──────────────┐      │     │
│  │  │              SyftHubClient (httpx)                       │      │     │
│  │  │  Handles all outbound HTTP to SyftHub                    │      │     │
│  │  └──────────────────────────┬───────────────────────────────┘      │     │
│  └─────────────────────────────┼───────────────────────────────────────┘     │
│                                │                                             │
│  ┌─────────────────┐           │                                             │
│  │  SQLite (app.db) │          │                                             │
│  │  via aiosqlite   │          │                                             │
│  └─────────────────┘           │                                             │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                    ═════════════╪══════════════
                      ngrok      │  HTTPS
                      tunnel     │
                    ═════════════╪══════════════
                                 │
┌────────────────────────────────▼─────────────────────────────────────────────┐
│                             SYFTHUB                                          │
│                        (External Marketplace)                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                    Interactions from Syft Space                      │     │
│  │                                                                     │     │
│  │  AUTHENTICATION                                                     │     │
│  │  ├─ POST /auth/login ─────────── marketplace login (email/pass)     │     │
│  │  └─ Token verification ───────── verify user identity on queries    │     │
│  │                                                                     │     │
│  │  ENDPOINT PUBLISHING                                                │     │
│  │  ├─ POST   /endpoints ────────── publish endpoint to marketplace    │     │
│  │  ├─ DELETE /endpoints/{slug} ─── unpublish endpoint                 │     │
│  │  └─ POST   /endpoints/sync ───── bulk sync on startup               │     │
│  │                                                                     │     │
│  │  HEALTH REPORTING                                                   │     │
│  │  └─ POST /endpoints/health ───── periodic health status updates     │     │
│  │                                                                     │     │
│  │  TUNNEL MANAGEMENT                                                  │     │
│  │  ├─ GET  /tunnel/credentials ─── fetch ngrok auth token + domain    │     │
│  │  └─ POST /tunnel/public-url ──── sync public URL after connect      │     │
│  │                                                                     │     │
│  │  ACCOUNTING                                                         │     │
│  │  └─ GET /accounting/credentials ─ fetch billing service creds       │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                    Interactions toward Syft Space                    │     │
│  │                                                                     │     │
│  │  ENDPOINT QUERIES (via ngrok tunnel)                                │     │
│  │  └─ POST /api/v1/endpoints/{slug}/query                            │     │
│  │     ├─ SyftHub user sends query with auth token                     │     │
│  │     ├─ Syft Space verifies token, enforces policies                 │     │
│  │     └─ Returns RAW search results / SUMMARY / BOTH                  │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                         External Services                                    │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐            │
│  │  ChromaDB       │  │  Weaviate      │  │  OpenAI-compatible  │            │
│  │  (local vector  │  │  (remote vector│  │  LLM API            │            │
│  │   database)     │  │   database)    │  │  (vLLM, OpenAI,     │            │
│  │                 │  │                │  │   etc.)              │            │
│  └────────────────┘  └────────────────┘  └─────────────────────┘            │
│         ▲                    ▲                      ▲                         │
│         └──── Dataset Types ─┘                      │                         │
│                (pluggable registry)         Model Types                       │
│                                            (pluggable registry)              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key Interaction Summary

### Syft Space → SyftHub


| Interaction            | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| **Auth**               | Login with marketplace credentials to get access tokens   |
| **Publish/Unpublish**  | Register endpoints on the marketplace for discovery       |
| **Startup Sync**       | Bulk-sync all published endpoints + public URL on boot    |
| **Health Reporting**   | Periodic heartbeat with status of all published endpoints |
| **Tunnel Credentials** | Fetch ngrok auth token and domain to establish the tunnel |


### SyftHub → Syft Space (via ngrok tunnel)


| Interaction          | Description                                                                                                                                                                                                            |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Endpoint Queries** | SyftHub users query published endpoints; Syft Space verifies the SyftHub token, enforces policies (rate limit, access, accounting), runs the RAG pipeline (search dataset → summarize with model), and returns results |


## Core Data Flow

A user creates **Datasets** (backed by ChromaDB/Weaviate) and **Models** (OpenAI-compatible LLMs), combines them into **Endpoints** with **Policies**, then **publishes** those endpoints to SyftHub where external users can query them through the ngrok tunnel.

---

## Endpoint Query Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CALLER                                                                 │
│  (Frontend via localhost OR SyftHub user via ngrok tunnel)              │
│                                                                         │
│  POST /api/v1/endpoints/{slug}/query                                    │
│  Headers: Authorization: Bearer <admin_key | syfthub_token>             │
│  Body: { messages, similarity_threshold, limit, temperature, ... }      │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. MIDDLEWARE STACK                                                     │
│                                                                         │
│  ┌──────────────────┐   ┌────────────────────┐   ┌───────────────┐     │
│  │ CORSMiddleware   │──▶│ TenantMiddleware    │──▶│ AdminKey      │     │
│  │ (allow origins)  │   │ (resolve tenant     │   │ Middleware    │     │
│  │                  │   │  from X-Tenant-Name │   │ (SKIPPED -   │     │
│  │                  │   │  or use default)    │   │  @public_route│     │
│  └──────────────────┘   └────────────────────┘   └───────────────┘     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. AUTHENTICATION                                                      │
│                                                                         │
│  get_verified_sender_email(request, tenant)                             │
│                                                                         │
│  Extract Bearer token from Authorization header                         │
│         │                                                               │
│         ├─── Token == admin_api_key? ──YES──▶ Return marketplace email  │
│         │                                                               │
│         └─── Otherwise ──▶ Call SyftHub verify_satellite_token()        │
│                                  │                                      │
│                                  ├── Valid ──▶ Return verified email    │
│                                  └── Invalid ──▶ 401 Unauthorized       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ sender_email
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. REQUEST ENRICHMENT                                                  │
│                                                                         │
│  AuthenticatedQueryRequest = QueryEndpointRequest + sender_email        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. ENDPOINT RESOLUTION                                                 │
│                                                                         │
│  endpoint = get_by_slug(slug, tenant_id)                                │
│         │                                                               │
│         ├── Not found ──▶ 404                                           │
│         └── Not published ──▶ 403                                       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. ACCOUNTING CREDENTIALS INJECTION                                    │
│                                                                         │
│  Fetch default marketplace → validate/refresh accounting creds          │
│  Inject { accounting_email, accounting_password, accounting_url }       │
│  into PolicyContext.metadata                                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  6. PRE-HOOK POLICY ENFORCEMENT                                         │
│                                                                         │
│  For each policy type attached to this endpoint:                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Access Policy (pre_hook)                                       │   │
│  │  ├─ Check sender_email against whitelist/blacklist              │   │
│  │  ├─ Blacklist takes priority over whitelist                     │   │
│  │  ├─ Supports glob patterns (*@company.com)                     │   │
│  │  └─ BLOCKED? ──▶ 403 "Access denied"                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                          │ pass                                         │
│  ┌───────────────────────▼─────────────────────────────────────────┐   │
│  │  Rate Limit Policy (pre_hook)                                   │   │
│  │  ├─ Check request count against limit (e.g., "50/m", "1000/h") │   │
│  │  ├─ Per-user or global scope                                    │   │
│  │  ├─ In-memory counter storage                                   │   │
│  │  └─ BLOCKED? ──▶ 403 "Rate limit exceeded"                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                          │ pass                                         │
│  ┌───────────────────────▼─────────────────────────────────────────┐   │
│  │  Accounting Policy (pre_hook)                                   │   │
│  │  ├─ Verify accounting credentials                               │   │
│  │  ├─ Check balance / pre-authorize transaction                   │   │
│  │  └─ BLOCKED? ──▶ 403 "Insufficient balance"                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ all policies passed
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  7. RAG PIPELINE (branched by endpoint.response_type)                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  response_type: RAW                                          │      │
│  │  └─ Dataset Search only                                      │      │
│  ├──────────────────────────────────────────────────────────────┤      │
│  │  response_type: SUMMARY                                      │      │
│  │  └─ Model Chat only                                          │      │
│  ├──────────────────────────────────────────────────────────────┤      │
│  │  response_type: BOTH                                         │      │
│  │  └─ Dataset Search → inject results → Model Chat             │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                        │
│  ┌─ DATASET SEARCH (if RAW or BOTH) ───────────────────────────────┐   │
│  │                                                                  │  │
│  │  dataset = get_by_id(endpoint.dataset_id)                        │  │
│  │  dataset_instance = DatasetTypeRegistry.get(dataset.dtype)       │  │
│  │                                                                  │  │
│  │  Extract query from messages (last user message)                 │  │
│  │           │                                                      │  │
│  │           ▼                                                      │  │
│  │  ┌─────────────────────────────────┐                             │  │
│  │  │  dataset_instance.search()      │                             │  │
│  │  │  ├─ ChromaDB: local similarity  │                             │  │
│  │  │  └─ Weaviate: remote similarity │                             │  │
│  │  └─────────────┬───────────────────┘                             │  │
│  │                │                                                 │  │
│  │                ▼                                                 │  │
│  │  ReferencesResponse {                                            │  │
│  │    documents: [{ document_id, content, metadata, score }],       │  │
│  │    provider_info: { search_engine }                              │  │
│  │  }                                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                │ references (top 3 docs used as context)               │
│                ▼                                                       │
│  ┌─ MODEL CHAT (if SUMMARY or BOTH) ──────────────────────────────┐    │
│  │                                                                  │  │
│  │  model = get_by_id(endpoint.model_id)                            │  │
│  │  model_instance = ModelTypeRegistry.get(model.dtype)             │  │
│  │                                                                  │  │
│  │  IF references exist:                                            │  │
│  │    Inject system message with top-3 document contents            │  │
│  │    "Use the following context to answer: [doc1] [doc2] [doc3]"   │  │
│  │           │                                                      │  │
│  │           ▼                                                      │  │
│  │  ┌─────────────────────────────────┐                             │  │
│  │  │  model_instance.chat()          │                             │  │
│  │  │  └─ OpenAI-compatible API call  │                             │  │
│  │  └─────────────┬───────────────────┘                             │  │
│  │                │                                                 │  │
│  │                ▼                                                 │  │
│  │  SummaryResponse {                                               │  │
│  │    id, model, message: { role, content, tokens },                │  │
│  │    finish_reason, usage: { prompt/completion/total_tokens }      │  │
│  │  }                                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  8. POST-HOOK POLICY ENFORCEMENT                                        │
│                                                                         │
│  PolicyContext now includes both request AND response                   │
│                                                                         │
│  For each policy type:                                                  │
│  ├─ Accounting Policy (post_hook) → confirm transaction, record usage   │
│  ├─ Rate Limit Policy (post_hook) → record consumption                  │
│  └─ Access Policy (post_hook) → audit logging                           │
│                                                                         │
│  Can still BLOCK response (e.g., accounting confirmation failure)       │
│  BLOCKED? ──▶ 403 (response discarded)                                  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  9. HTTP RESPONSE (200 OK)                                              │
│                                                                         │
│  QueryEndpointResponse {                                                │
│    "summary": { ... } | null,      ◄── present if SUMMARY or BOTH       │
│    "references": { ... } | null    ◄── present if RAW or BOTH           │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                          FRONTEND                                       │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Framework        │  Vue 3 (Composition API, <script setup>)  │     │
│  │  Language          │  TypeScript                               │     │
│  │  State Management  │  Pinia                                    │     │
│  │  Routing           │  Vue Router                               │     │
│  │  HTTP Client       │  Axios                                    │     │
│  │  UI Components     │  shadcn/vue (Radix Vue primitives)        │     │
│  │  Icons             │  lucide-vue-next                          │     │
│  │  Styling           │  Tailwind CSS                             │     │
│  │  Build Tool        │  Vite                                     │     │
│  │  Package Manager   │  Bun                                      │     │
│  │  Linting           │  ESLint + Oxlint                          │     │
│  │  Formatting        │  Prettier                                 │     │
│  │  Testing           │  Vitest (unit), Playwright (e2e)          │     │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                          BACKEND                                        │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  Framework        │  FastAPI (async)                           │     │
│  │  Language          │  Python 3.12                               │     │
│  │  Server            │  Uvicorn (ASGI)                            │     │
│  │  ORM               │  SQLModel + SQLAlchemy                     │     │
│  │  Database           │  SQLite (via aiosqlite)                   │     │
│  │  Migrations        │  Alembic                                   │     │
│  │  Validation        │  Pydantic v2                               │     │
│  │  HTTP Client       │  httpx (async)                             │     │
│  │  File Watching     │  watchdog                                  │     │
│  │  Async Bridging    │  janus (sync↔async queues)                 │     │
│  │  Logging           │  loguru                                    │     │
│  │  Error Tracking    │  Sentry SDK                                │     │
│  │  Package Manager   │  uv                                        │     │
│  │  Formatting        │  Black + isort                             │     │
│  │  Linting           │  Ruff / flake8                             │     │
│  │  Type Checking     │  mypy                                      │     │
│  │  Testing           │  pytest                                    │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                       AI / ML SERVICES                                  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  LLM Integration   │  OpenAI SDK (any OpenAI-compatible API)  │     │
│  │  Vector DB (local)  │  ChromaDB                                │     │
│  │  Vector DB (remote) │  Weaviate                                │     │
│  │  Doc Processing    │  Docling (PDF, DOCX, etc.)                │     │
│  │  ML Runtime        │  PyTorch + TorchVision                    │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                     INFRASTRUCTURE                                      │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Tunneling         │  ngrok (Python SDK)                       │     │
│  │  Containerization  │  Docker + Docker Compose                  │     │
│  │  Desktop Wrapper   │  Tauri (Rust)                             │     │
│  │  CI/CD             │  GitHub Actions                           │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                    EXTERNAL SERVICES                                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Marketplace       │  SyftHub (endpoint publishing, auth,     │     │
│  │                     │  tunnel creds, accounting, feedback)    │     │
│  │  Accounting        │  External billing service (via SyftHub)  │     │
│  │  Error Monitoring  │  Sentry                                  │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Datasets, Models, Policies & Endpoints

### Plugin Registry Architecture

All three resource types (Datasets, Models, Policies) use a **pluggable registry pattern**. Built-in types are registered at startup; custom types can be added by implementing an interface and registering with the registry.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       STARTUP (main.py)                                 │
│                                                                         │
│  register_dataset_types(DATASET_TYPE_REGISTRY)                          │
│  register_model_types(MODEL_TYPE_REGISTRY)                              │
│  register_policy_types(POLICY_TYPE_REGISTRY)                            │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │ DatasetType      │  │ ModelType        │  │ PolicyType       │        │
│  │ Registry         │  │ Registry         │  │ Registry         │        │
│  │                  │  │                  │  │                  │        │
│  │ "local_file"     │  │ "openai"         │  │ "access"         │        │
│  │ "remote_weaviate"│  │                  │  │ "rate_limit"     │        │
│  │                  │  │                  │  │ "accounting"     │        │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘       │
│           │                     │                      │                 │
│           ▼                     ▼                      ▼                 │
│  Each registry provides:                                                │
│  ├─ register(cls)          Register a new type                          │
│  ├─ get(name)              Retrieve type class by name                  │
│  ├─ list()                 List all registered type names               │
│  └─ is_registered(name)   Check availability                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Entity Relationships

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   ┌──────────────┐                          ┌──────────────┐            │
│   │   DATASET     │                          │    MODEL     │            │
│   │              │                          │              │            │
│   │  id          │                          │  id          │            │
│   │  name        │                          │  name        │            │
│   │  dtype ──────┼──► DatasetTypeRegistry   │  dtype ──────┼──► ModelTypeRegistry
│   │  configuration│  (e.g., "local_file")   │  configuration│  (e.g., "openai")
│   │  tenant_id   │                          │  tenant_id   │            │
│   │  provisioner_│                          │              │            │
│   │   state_id ──┼──► ProvisionerState      │              │            │
│   └──────┬───────┘                          └──────┬───────┘            │
│          │                                         │                     │
│          │  dataset_id (0..1)          model_id (0..1)                   │
│          │                                         │                     │
│          └──────────────┐     ┌────────────────────┘                     │
│                         ▼     ▼                                          │
│                   ┌──────────────────┐                                   │
│                   │    ENDPOINT       │                                   │
│                   │                  │                                   │
│                   │  id              │                                   │
│                   │  name, slug      │                                   │
│                   │  dataset_id ─────┼──► FK to Dataset (optional)      │
│                   │  model_id ───────┼──► FK to Model (optional)        │
│                   │  response_type   │   (at least one required)        │
│                   │  published       │                                   │
│                   │  published_to    │   ┌──────────────┐               │
│                   │  tenant_id       │   │   POLICY      │               │
│                   │                  │◄──┤              │               │
│                   │                  │   │  id          │               │
│                   └──────────────────┘   │  name        │               │
│                          ▲               │  policy_type ┼──► PolicyTypeRegistry
│                          │               │  configuration│  (e.g., "rate_limit")
│                          │               │  endpoint_id ┼──► FK to Endpoint
│                          │               │  tenant_id   │               │
│                          │               └──────────────┘               │
│                          │                      │                        │
│                          └──────────────────────┘                        │
│                           1 endpoint ◄── many policies                   │
│                                                                          │
│   ┌──────────────────┐                                                  │
│   │ PROVISIONER STATE │  Shared across datasets of same type            │
│   │                  │                                                  │
│   │  id             │                                                  │
│   │  dtype          │  (e.g., "local_file")                            │
│   │  state (dict)   │  Runtime state from provisioner.start()          │
│   │  status         │  STOPPED | STARTING | RUNNING | STOPPING | ERROR │
│   └──────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────────┘

RELATIONSHIP RULES:
  - An Endpoint MUST have at least one of dataset_id or model_id
  - An Endpoint can have MANY policies (one-to-many)
  - A Dataset can be linked to MANY endpoints (one-to-many)
  - A Model can be linked to MANY endpoints (one-to-many)
  - A Policy belongs to exactly ONE endpoint
  - response_type determines which resources are used at query time:
      "raw"     → dataset only
      "summary" → model only
      "both"    → dataset + model (search results fed as context to model)
```

### Dataset Types

Each dataset type implements the `BaseDatasetType` interface and provides search, ingestion, and health-check capabilities.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BaseDatasetType Interface                                              │
│                                                                         │
│  Required:                                                              │
│  ├─ search(ctx, query, params) → SearchResult     Core search           │
│  ├─ healthcheck() → HealthcheckResponse            Health status        │
│  ├─ configuration_schema() → JSON Schema           Config definition    │
│  ├─ validate_configuration(config) → None          Async validation     │
│  └─ connection_fields() → list[str]                Shared provisioner   │
│                                                     fields              │
│  Optional extensions:                                                   │
│  ├─ IngestableDatasetType                                               │
│  │   ├─ ingest(ctx, request) → None                Ingest data          │
│  │   └─ delete(ctx) → None                         Delete dataset       │
│  └─ FileIngestableDatasetType                                           │
│      ├─ watched_paths() → list[str]                Dirs to monitor      │
│      └─ allowed_extensions() → set[str]            e.g., {".pdf"}       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Built-in Implementations:                                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "local_file" — ChromaDB Local                              │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ collectionName: str         ChromaDB collection         │       │
│  │  ├─ httpPort: int (8100)        ChromaDB server port        │       │
│  │  ├─ ingestFileTypeOptions:      Allowed file extensions     │       │
│  │  │   [".pdf",".txt",".html",   (for ingestion)             │       │
│  │  │    ".xlsx",".docx",".md",                                │       │
│  │  │    ".csv",".json"]                                       │       │
│  │  └─ filePaths:                  Watched directories         │       │
│  │      [{path, description}]      with descriptions           │       │
│  │                                                             │       │
│  │  Connection fields: ["httpPort"]                             │       │
│  │  Provisioner: LocalChromaDBProvisioner (manages subprocess) │       │
│  │  Capabilities: search, ingest, file-watching, healthcheck   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "remote_weaviate" — Weaviate Remote                        │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ http_url: str               Weaviate HTTP endpoint      │       │
│  │  ├─ grpc_url: str               Weaviate gRPC endpoint      │       │
│  │  ├─ api_key: str                Authentication key           │       │
│  │  ├─ collection_name: str        Target collection            │       │
│  │  ├─ headers: dict | null        Extra HTTP headers           │       │
│  │  ├─ default_similarity_threshold: float (0.5)               │       │
│  │  ├─ content_property: str | null  Main content field         │       │
│  │  ├─ metadata_properties: list | null                        │       │
│  │  └─ filters: WeaviateFilter | null                          │       │
│  │                                                             │       │
│  │  Connection fields: ["http_url","grpc_url","api_key",       │       │
│  │                       "collection_name"]                    │       │
│  │  Provisioner: None (external service)                       │       │
│  │  Capabilities: search, healthcheck                          │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Model Types

Each model type implements the `BaseModelType` interface for LLM chat completions.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BaseModelType Interface                                                │
│                                                                         │
│  Required:                                                              │
│  ├─ chat(ctx, messages, params) → ChatResult       Core chat            │
│  ├─ healthcheck() → HealthcheckResponse             Health status       │
│  ├─ configuration_schema() → JSON Schema            Config definition   │
│  └─ enabled() → bool                                Feature flag        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Built-in Implementation:                                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "openai" — OpenAI-compatible API                           │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ api_key: str                API authentication          │       │
│  │  ├─ model: str ("gpt-3.5-turbo")  Model identifier         │       │
│  │  ├─ base_url: str               Custom endpoint URL         │       │
│  │  │   ("https://api.openai.com/v1")  (vLLM, Ollama, etc.)  │       │
│  │  └─ system_prompt: str ("")     Default system prompt       │       │
│  │                                                             │       │
│  │  Works with: OpenAI, vLLM, Ollama, any OpenAI-compatible   │       │
│  │  Capabilities: chat completions, healthcheck                │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Policy Types

Each policy type implements `pre_hook` and `post_hook` methods that run before and after endpoint query execution. Multiple policies of the same type can be attached to one endpoint — the type decides its own aggregation logic.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BasePolicyType Interface                                               │
│                                                                         │
│  Required:                                                              │
│  ├─ pre_hook(configs, context) → PolicyContext   Before query           │
│  │   Can: block request, modify context, inject metadata                │
│  ├─ post_hook(configs, context) → PolicyContext  After query            │
│  │   Can: block response, modify response, record usage                 │
│  ├─ configuration_schema() → JSON Schema         Config definition      │
│  └─ validate_config(config) → dict               Async validation       │
│                                                                         │
│  Notes:                                                                 │
│  ├─ Hooks receive ALL configs for that type on the endpoint             │
│  ├─ Each type decides aggregation: AND, OR, or custom                   │
│  └─ Raise PolicyViolationError to block (→ HTTP 403)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Built-in Implementations:                                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "access" — Access Control                                  │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ allowed_users: list[str]    Glob patterns               │       │
│  │  │   e.g., ["*@company.com", "admin-*@*"]                  │       │
│  │  └─ denied_users: list[str]     Glob patterns (priority)    │       │
│  │                                                             │       │
│  │  Aggregation: OR — if ANY policy allows, access granted     │       │
│  │  Deny always overrides allow                                │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "rate_limit" — Rate Limiting                               │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ limit: str                  "N/unit" (e.g., "50/m")     │       │
│  │  ├─ scope: str                  "per_user" | "global"       │       │
│  │  └─ applied_to: list[str]       Glob patterns (default: *) │       │
│  │                                                             │       │
│  │  Aggregation: AND — ALL limits must pass                    │       │
│  │  In-memory counters, sorted most-restrictive-first          │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  "accounting" — Usage Billing                               │       │
│  │                                                             │       │
│  │  Config:                                                    │       │
│  │  ├─ price: float                Price per unit              │       │
│  │  ├─ pricing_mode: str           "per_call"                  │       │
│  │  └─ applied_to: list[str]       Glob patterns (default: *) │       │
│  │                                                             │       │
│  │  Aggregation: AND — ALL must succeed                        │       │
│  │  Pre-hook: create transaction; Post-hook: confirm it        │       │
│  │  Credentials injected via PolicyContext.metadata             │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### How It All Connects: Building an Endpoint

```
  USER WORKFLOW                           SYSTEM INTERNALS
  ──────────────                          ─────────────────

  1. Create Dataset                       Dataset entity saved to DB
     ├─ Pick type: "local_file"           dtype → DatasetTypeRegistry
     └─ Fill config: collectionName,      configuration validated via
        httpPort, filePaths               type.validate_configuration()
                                          Provisioner started if needed
                    │
                    ▼
  2. Create Model                         Model entity saved to DB
     ├─ Pick type: "openai"               dtype → ModelTypeRegistry
     └─ Fill config: api_key,             configuration validated via
        model, base_url                   type.validate_configuration()
                    │
                    ▼
  3. Create Endpoint                      Endpoint entity saved to DB
     ├─ Link dataset_id ────────────────► FK to Dataset
     ├─ Link model_id ─────────────────► FK to Model
     ├─ Set response_type: "both" ──────► Determines query behavior
     └─ Set slug, name, description
                    │
                    ▼
  4. Add Policies                         Policy entities saved to DB
     ├─ Access: allow *@myorg.com ──────► endpoint_id FK to Endpoint
     ├─ Rate limit: 100/h per_user ────► endpoint_id FK to Endpoint
     └─ Accounting: $0.01/call ────────► endpoint_id FK to Endpoint
                    │
                    ▼
  5. Publish to SyftHub                   SyftHubClient.publish_endpoint()
     └─ Endpoint becomes queryable ────► External users discover via
        via ngrok tunnel                  marketplace and send queries
```

### Adding a Custom Type

To extend the system with a new dataset, model, or policy type:

```
  DATASET TYPE                MODEL TYPE                POLICY TYPE
  ────────────                ──────────                ───────────

  1. Create module under      1. Create module under    1. Create module under
     dataset_types/              model_types/              policy_types/
     my_type/                    my_type/                  my_type/
     my_type.py                  my_type.py                my_type.py

  2. Implement interface:     2. Implement interface:   2. Implement interface:
     BaseDatasetType             BaseModelType             BasePolicyType
     ├─ search()                 ├─ chat()                 ├─ pre_hook()
     ├─ healthcheck()            ├─ healthcheck()          ├─ post_hook()
     ├─ configuration_schema()   ├─ configuration_schema() ├─ configuration_schema()
     └─ validate_configuration() └─ enabled()              └─ validate_config()

  3. (Optional) Add           3. Register in            3. Register in
     provisioner class           __init__.py:              __init__.py:
     if type needs               registry.register_       registry.register_
     managed infra               model_type(MyType)        policy_type(MyType)

  4. Register in
     __init__.py:
     registry.register_
     lazy_dataset_type(...)
```
