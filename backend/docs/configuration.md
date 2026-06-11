# Configuration

All configuration is environment-based, loaded in
[`syft_space/config.py`](../syft_space/config.py). Every variable is prefixed
`SYFT_`.

## Environment variables

### Core

| Variable | Default | Description |
| --- | --- | --- |
| `SYFT_HOST` | `0.0.0.0` | Server bind address |
| `SYFT_PORT` | `8080` | Server port |
| `SYFT_DEBUG` | `false` | FastAPI debug mode (verbose errors, migration fallback) |
| `SYFT_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `SYFT_LOG_FILE` | `~/.syft-space/logs/syft-space-server.log` | Log file path (enables rotation) |

### Database

| Variable | Default | Description |
| --- | --- | --- |
| `SYFT_SQLITE_DB_PATH` | `~/.syft-space/app.db` | Main application database |
| `SYFT_ANALYTICS_DB_PATH` | `~/.syft-space/analytics.db` | Separate analytics event database |
| `SYFT_RESET_DB` | `false` | **Destructive** — drop & recreate all tables on startup |

> The backend uses **two SQLite databases**: the main app DB and an isolated
> analytics DB. Each has its own migration chain. See
> [Migrations](./migrations.md).

### Authentication & tenancy

| Variable | Default | Description |
| --- | --- | --- |
| `SYFT_ADMIN_API_KEY` | `""` | Admin API key. **Empty = dev mode (no auth).** |
| `SYFT_ENABLE_MULTI_TENANCY` | `false` | Enable per-tenant isolation |
| `SYFT_DEFAULT_TENANT_NAME` | `root` | Name of the auto-created default tenant |

### Marketplace, tunnel & health

| Variable | Default | Description |
| --- | --- | --- |
| `SYFT_DEFAULT_MARKETPLACE_URL` | `https://syfthub.openmined.org` | Default SyftHub instance |
| `SYFT_PUBLIC_URL` | `None` | Public URL advertised for inbound queries |
| `SYFT_HEARTBEAT_ENABLED` | `true` | Periodically report endpoint health to marketplaces |
| `SYFT_HEALTH_CHECK_INTERVAL` | `30.0` | Seconds between endpoint health checks |

### Models & payments

| Variable | Default | Description |
| --- | --- | --- |
| `SYFT_CHAT_TIMEOUT_SECONDS` | `60.0` | Timeout for model chat calls |
| `SYFT_TEMPO_TESTNET` | `true` | Use the Tempo **testnet** for MPP crypto payments (`false` = mainnet) |
| `SYFT_STRIPE_API_URL` | `https://api.stripe.com` | Stripe API base URL |
| `SYFT_XENDIT_API_URL` | `https://api.xendit.co` | Xendit API base URL |

> Verify defaults against [`config.py`](../syft_space/config.py) — it is the
> source of truth and may add fields over time.

## Authentication

The backend has two layers of identity, enforced by `AdminKeyMiddleware`:

- **Admin routes (the dashboard API).** Protected by `SYFT_ADMIN_API_KEY`.
  - **Production:** set the key; every protected request must send
    `Authorization: Bearer <key>`.
  - **Dev mode:** leave it empty to disable admin auth entirely.
- **Public routes** (decorated `@public_route`, e.g. `POST
  /endpoints/{slug}/query`, gateway invoice/balance routes, health). These skip
  the admin key. Routes that identify an end user verify a **SyftHub token**
  instead. See [API Overview › Authentication](./api-overview.md#authentication).

## Multi-tenancy

When `SYFT_ENABLE_MULTI_TENANCY=true`:

- Send an `X-Tenant-Name` header to scope requests to a tenant.
- All data (datasets, models, endpoints, policies, wallets, …) is isolated per
  tenant.
- A default tenant (`SYFT_DEFAULT_TENANT_NAME`) is created on startup.

With multi-tenancy **off**, everything runs under the single default tenant and
the header is unnecessary.

## Docker

```bash
# Build the frontend first — it is served as static files by the backend
cd frontend && bun install && bun run build && cd ..

# Build the image (Dockerfile at repo root)
docker build -t syft-space-server .
```

Run with env vars:

```bash
docker run -d -p 8080:8080 \
  -e SYFT_ADMIN_API_KEY=your-secret-key \
  -e SYFT_SQLITE_DB_PATH=/data/app.db \
  -e SYFT_ANALYTICS_DB_PATH=/data/analytics.db \
  -v syft-data:/data \
  syft-space-server
```

Or with an env file / Compose:

```bash
cp .env.example .env   # edit values
docker compose up -d
```

## Development commands

Run from `backend/`:

```bash
uv run --extra lint ruff format .   # format
uv run --extra lint ruff check .    # lint
mypy .                              # type-check
pytest                              # tests

pre-commit install                  # install git hooks
pre-commit run --all-files          # run hooks manually
```
</content>
