# API Overview

> **The exhaustive, always-current reference is the running app itself:**
> Swagger UI at **`/docs`** and the raw schema at **`/openapi.json`**. This page
> describes the *shape* of the API — base path, auth, conventions, and where each
> resource lives — not every field. Trust the OpenAPI schema for specifics.

## Base path

All application routes are mounted under **`/api/v1`**. The frontend is served
as static files under `/frontend`; `/` redirects there (or to `/docs` if no
frontend build is present).

## Authentication

There are two identities, enforced by `AdminKeyMiddleware`:

| Caller | Routes | How |
| --- | --- | --- |
| **Admin** (the dashboard) | Everything except `@public_route` | `Authorization: Bearer <SYFT_ADMIN_API_KEY>`. If the key is unset, the server is in **dev mode** and admin auth is skipped. |
| **End user** | Public routes that identify a user (e.g. query, gateway balance/invoices) | A **SyftHub token** in `Authorization: Bearer …`, verified against SyftHub. |
| **Anyone** | Open public routes (health, webhooks) | None. |

Public routes are marked in code with the `@public_route` decorator and
discovered at startup. See [Configuration ›
Authentication](./configuration.md#authentication).

## Conventions

- **Content type:** JSON, except feedback (multipart form) and webhooks.
- **Multi-tenancy:** when enabled, scope requests with an `X-Tenant-Name`
  header. Off by default → single tenant, header optional.
- **Identifiers:** datasets and models are addressed by `name`, endpoints by
  `slug`, policies/wallets/invoices by UUID.
- **Errors:** standard FastAPI error responses — `4xx`/`5xx` with a JSON
  `detail`. Common codes: `401` (bad/missing token), `403` (policy denied /
  unpublished), `402` (payment required, MPP), `404` (not found), `409`
  (conflict, e.g. duplicate slug).

## Resource map

Each resource is mounted under `/api/v1`. Open `/docs` for the full operation
list per group.

| Resource | Base path | What it covers |
| --- | --- | --- |
| **Datasets** | `/datasets` | CRUD, type discovery + schemas, source browsing, health, provisioner admin |
| **Models** | `/models` | CRUD, type discovery + schemas, type actions, health |
| **Endpoints** | `/endpoints` | CRUD, slug validation, archive/unarchive, **query**, preview, publish/unpublish |
| **Policies** | `/policies` | CRUD, type discovery + schemas |
| **Ingestion** | `/ingestion/datasets/{id}` | Status, jobs, start/stop, retry failed |
| **Wallets** | `/wallets` | List/get/delete; `mpp/*` (generate, import, address) and `gateway/*` (stripe, xendit) creation |
| **Payments** | `/payments` | `mpp/*` balance & transactions; `gateway/*` invoices, balances, transactions, provider webhooks |
| **Analytics** | `/analytics` | Summary, time-series, top users, word cloud |
| **Marketplaces** | `/marketplaces` | Register (+ OTP), connect, username check, list/get |
| **Settings** | `/settings` | Public URL, proxy (ngrok) status/config, diagnostics toggle |
| **Feedback** | `/feedback` | Submit feedback / bug report (multipart, with screenshot) |
| **Tenants** | `/tenants` | Create/list/get (multi-tenancy) |
| **System** | `/health` | Liveness check (public) |

## Public (unauthenticated-by-admin-key) routes

These bypass the admin key. Several still require a SyftHub token to identify the
end user.

| Route | Auth | Purpose |
| --- | --- | --- |
| `GET /api/v1/health` | none | Liveness |
| `POST /api/v1/endpoints/{slug}/query` | SyftHub token | Query a published endpoint |
| `GET /api/v1/datasets/{name}/health` | none | Dataset health |
| `GET /api/v1/models/{name}/health` | none | Model health |
| `POST /api/v1/feedback/` | none | Submit feedback |
| `POST /api/v1/payments/gateway/wallets/{id}/invoices` | SyftHub token | Buy credits (create invoice) |
| `GET /api/v1/payments/gateway/wallets/{id}/balance` | SyftHub token | A user's own prepaid balance |
| `GET /api/v1/payments/gateway/wallets/{id}/invoices/me` | SyftHub token | A user's own invoices |
| `GET /api/v1/payments/gateway/wallets/{id}/transactions/me` | SyftHub token | A user's own transactions |
| `POST /api/v1/payments/gateway/{provider}/webhooks` | provider signature | Stripe/Xendit callbacks |

## The query endpoint

`POST /api/v1/endpoints/{slug}/query` is the most important route and has the
richest behavior (token verification, policy enforcement, the RAG pipeline,
payment challenges). It has its own deep-dive: **[Query Flow](./query-flow.md)**.
</content>
