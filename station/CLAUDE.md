# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in
`station/` — the Syft Station control plane. It supplements the repo-root
CLAUDE.md; where they conflict, this file wins for code under `station/`.

## Project Overview

Syft Station is the control plane for running member-owned Syft Spaces on
shared Kubernetes infrastructure. Members sign in with SyftHub and request a
space; the admin reviews requests; approved spaces are provisioned onto the
cluster as labeled resource bundles (Deployment/PVC/Service/Ingress/Secret).
The station is a FastAPI backend + Vue 3 frontend, deployed in production as
ONE in-cluster pod (the backend serves the built frontend statically).

Design doc: `station.md` at the repo root (uncommitted, kept current).

## Naming rule (important)

- **"Syft Station" is the brand** — user-visible copy, docs headings, URLs.
- **`cluster` is the integration surface** — everything syft-space or a k8s
  Secret references keeps the name: `SYFT_CLUSTER_CREDITS_*`,
  `SYFT_CLUSTER_MANAGED_BY`, `WalletType.CLUSTER`, `cluster_per_request`.
  Never rename these to "station"; never write "cluster" in new user-visible
  station copy.
- The Kubernetes substrate is always spelled out as "the Kubernetes cluster".

## Architecture

### Backend (`station/backend`, package `syft_station`)

- FastAPI + SQLModel + aiosqlite + Alembic, mirroring syft-space conventions.
- Domain-driven components in `syft_station/components/`, each with the same
  file split as syft-space: `entities.py`, `handlers.py`, `repository.py`,
  `routes.py`, `schemas.py` (plus `interfaces.py` where a seam exists).
- Components:
  - `auth/` — SyftHub sign-in proxy (hub tokens are used once and discarded;
    the station issues its own signed session cookie). Role = admin iff
    email == `SYFT_STATION_ADMIN_EMAIL`.
  - `setup/` — first-run settings (domain + supported version);
    `onboarded ⇔ domain != ""`.
  - `requests/` — space-request lifecycle:
    PENDING → PROVISIONING → ACTIVE, plus REJECTED / FAILED (retryable) /
    DELETED / WITHDRAWN (member withdraws own PENDING request; kept as a
    state so the admin retains visibility). Only PENDING / PROVISIONING /
    ACTIVE reserve a subdomain.
  - `spaces/` — provisioned-space registry + space admin-token lifecycle
    (one-time reveal, regenerate). Runtime status is NOT stored — Kubernetes
    is the source of truth for it.
  - `provision/` — the `Provisioner` protocol. `MockProvisioner` fakes it
    without a cluster (subdomain containing "fail" → FAILED, to exercise
    retry); `K8sProvisioner` is the real one.
  - `images/` — lists available syft-space image tags from the container
    registry (anonymous GHCR pull flow) for the admin's version picker.
    Newest-first with created dates; `latest` resolved by digest match;
    cached in memory (immutable per-tag memo + short list TTL).
  - `shared/` — `database.py` (AsyncDatabase + AsyncBaseRepository, WAL
    pragmas), logging.
- Routes are built with the `build_*_routes(handler) -> APIRouter` factory
  pattern and mounted under `/api/v1`.
- Config: pydantic-settings with env prefix `SYFT_STATION_` (`config.py`).
  SQLite at `~/.syft-station/app.db`.
- CLI (`cli.py`, console script `syft-station`): internal-only — `server`
  (wraps uvicorn; container ENTRYPOINT) and `upgrade-db` (Alembic).
  It is NOT a user-facing tool; Helm is the installer.

### Frontend (`station/frontend`)

Vue 3 + TypeScript + Tailwind + shadcn/ui + Pinia — identical stack and
conventions to the root `frontend/` (its CLAUDE.md applies: shadcn/ui
components, lucide-vue-next icons, `<script setup>`, bun not npm).
`stores/station.ts` is server-backed via the typed client in `src/api/`
(fetch wrapper + endpoint modules mirroring the backend schemas); the Vite
dev server (:5174) proxies `/api` to the backend on :8090 so the session
cookie stays same-origin. Still mocked pending its backend: the log tail.

## Development Commands

### Backend (from `station/backend/`)

```bash
uv sync --extra dev            # install deps (creates .venv + uv.lock)
uv run uvicorn syft_station.main:app --reload --port 8090
uv run pytest                  # tests
uv run --extra lint ruff check .    # lint
uv run --extra lint ruff format .   # format
uv run alembic revision --autogenerate -m "..."   # new migration
```

### Frontend (from `station/frontend/`)

```bash
bun install
bun dev                        # :5174
bun run lint && bun run typecheck && bun run format
```

### Kubernetes dev environment

ONE Helm chart (`station/chart/`) is the source of truth for every
deployment — dev is that same chart with `values-dev.yaml` (ephemeral
ChromaDB, locally-built `:dev` image, `*.localhost` hosts, no NetworkPolicy/
HPA/TLS). Two inner loops on a k3d cluster (prod parity with the k3s install
story), driven by the `justfile`:

```bash
just cluster                   # k3d + shared deps (ChromaDB, docling) only
just dev up admin=you@org.com  # station on the HOST (uvicorn --reload),
                               #   spaces provisioned into k3d over kubeconfig
                               #   (`just dev` alone defaults to `up`)
just dev down                  # tear down cluster + host state (~/.syft-station)
just build-ui                  # build frontend/dist -> served by just dev at /ui
just dev-ui                    # OR: Vite HMR for the frontend (2nd terminal)
just up  admin=you@org.com     # FULL in-cluster: the station pod via Helm
just down                      # tear the cluster down (host state kept)
just space-image tag=x         # build + import an UNPUBLISHED syft-space build
```

`just dev` is the everyday loop — edit backend code, uvicorn reloads, no
image rebuild; the host station talks to k3d via `~/.kube/config` and
provisions space pods *into* the cluster. For the UI, the backend serves the
packaged `syft_station/ui` if present (the image), else the sibling
`frontend/dist` (main.py) — same in-place pattern as syft-space. So
`just build-ui` (plain `vite build` → `frontend/dist`) makes `just dev` serve
the UI at `:8090/ui`; re-run it after frontend edits (uvicorn --reload watches
only `.py`), or use `just dev-ui` for live HMR. `just up` is the parity check
(in-cluster DNS, RBAC, the real deployed pod, frontend served statically from
the image).

The station is at `http://station.localhost` in BOTH loops — in `just dev`
the chart's dev host-route (an ExternalName Service named `syft-station` +
an Ingress, `chart/templates/station/host-route.yaml`) proxies that name
through Traefik to the host process, and makes the spaces' default
in-cluster credits URL (`http://syft-station:8090`) resolve to the host.
Dev therefore uses the same URLs and the same onboarding as prod: setup
suggests `station.localhost` as the domain (derived from
`SYFT_STATION_PUBLIC_URL`), and spaces resolve at
`<subdomain>.station.localhost` (via the k3d loadbalancer on :80;
`*.localhost` → 127.0.0.1 in browsers, no DNS setup). Space URLs are minted
plain-http in dev (`SYFT_STATION_SPACE_SCHEME` / `spaces.scheme` — no certs).
The `admin` argument sets
`SYFT_STATION_ADMIN_EMAIL` — without it every sign-in gets the member role.
An optional `hub=http://syfthub.localhost:8080` argument sets
`SYFT_STATION_SYFTHUB_URL` (omitted → the production SyftHub default).
`syfthub.localhost` is the canonical name for a host-run local hub: browsers
and host processes resolve it to loopback natively, and `cluster-dns` maps it
to the host machine inside the cluster — the SAME hub URL works everywhere
(never use `host.k3d.internal` or plain `localhost`, which only resolve in
one of those worlds). CORS for the hub's browser origin is derived from it. Both loops self-seed the syft-space `:dev`
image — built + imported only when missing from the cluster node — and set
`SYFT_STATION_SPACE_VERSION` so onboarding suggests it. An explicit
`space=tag` argument force-rebuilds that tag (the flow after syft-space code
changes); `space=none` runs on published images only. Spaces in both loops
see the host's home directory read-only at `~/host-home`: the flag
(`spaces.hostMount` / `SYFT_STATION_SPACE_HOST_MOUNT`, default off) mounts
the node's `/mnt/host-home` into every space inside the space's home (the
dataset file browser is rooted at home and rejects paths outside it), and
the dev cluster maps `$HOME` to that node path at creation. The chart preserves the session secret
across `helm upgrade` (via a live `lookup`), so cookies survive redeploys.
Otherwise spaces pull the published image (`ghcr.io/openmined/syft-space`)
at whatever tag the admin picks; nothing is baked in.

Layout: `station/chart/` — the Helm chart (station + shared ChromaDB/docling,
RBAC, NetworkPolicy; values drive dev↔prod). `syft_station/k8s/space/` — the
per-space bundle templates the provisioner renders at runtime (NOT part of
the chart). For quick host-side hacking without a cluster, the backend runs
directly with `MockProvisioner` (`SYFT_STATION_PROVISIONER` defaults to
`mock`; see Development Commands).

## Development Patterns

- Follow syft-space patterns exactly: handlers own business logic and raise
  `HTTPException`; repositories own persistence; routes are thin.
- Alembic from day one — schema changes always come with a migration
  (`upgrade-db` runs them; never silent auto-migrate in production).
- Tests mirror syft-space style: handler/repository-level with temp-file
  SQLite fixtures; external HTTP (SyftHub) stubbed via `httpx.MockTransport`
  through the client's `_build_http_client` seam.
- Space admin tokens: plaintext is stored only until first reveal, then
  cleared; regenerate mints a new token.
- Zero code coupling with syft-space: the only contract is the syft-space
  container image + `SYFT_*` env vars + its health endpoint. Never import
  from `syft_space`.
- Always run lint/typecheck (and backend tests) after changes.
