# Syft Station

> **Spin up your own Space, dock it to the Station.** Share the station, never your data.

Control plane for running a Syft Station: shared infrastructure (ChromaDB +
docling-serve) plus a signup/approval flow that provisions individual
syft-space instances on Kubernetes. Design: see `station.md` at the repo
root.

Independent of syft-space by design — the only contract between them is the
syft-space container image, its `SYFT_*` env vars, and its health endpoint.

## Structure

- `backend/` — FastAPI control-plane server (scaffold; SyftHub sign-in proxy,
  request queue, k8s provisioner to come)
- `frontend/` — Vue 3 + TypeScript + Tailwind + shadcn/ui (same stack as
  syft-space). Currently a **UX prototype with mocked data** for the member
  signup flow and the admin dashboard.

## Frontend prototype

```bash
cd frontend
bun install
bun dev          # http://localhost:5174
```

All data is in-memory and mocked (resets on refresh):

- Sign in with any email/password (mock SyftHub sign-in; profile is prefabbed
  from the email).
- Member view (`/`): request a space, track "My requests", one-time API key
  reveal when a space goes active.
- Admin view (`/admin`): pending request queue with the approve
  (review-and-tweak) modal and reject flow; Spaces tab with health, restart,
  delete, purge.
- Approvals "provision" after a simulated delay, then appear under Spaces.
  Name a space with `fail` in it to see the failure + retry path.

## Backend

```bash
cd backend
uv venv -p 3.12 && uv pip install -e .
uv run uvicorn syft_station.main:app --reload --port 8090
```
