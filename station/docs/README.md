# Syft Station — implementation docs

Documentation of how the station is built, one page per area. The audience
is someone working on the code; for what the station *is* and how to run
one, start at the [station README](../README.md).

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI control plane (`syft_station` package) |
| `frontend/` | Vue 3 + TypeScript + shadcn/ui dashboard, served statically by the backend |
| `chart/` | The Helm chart (station + shared backends; dev and prod are the same chart) |
| `backend/syft_station/k8s/space/` | Per-space manifest templates the station renders at runtime |
| `justfile` | The dev loops ([deployment.md](deployment.md#the-dev-loops)) |
| `docs/` | These pages; diagram sources and renders in `docs/assets/` |

## Reading order

1. **[architecture.md](architecture.md)** — the shape of the system: one
   pod, the component layout, wiring, configuration, and the contracts that
   hold it together. Read this first; every other page assumes it.
2. **[auth.md](auth.md)** — how identities enter the station: SyftHub
   sign-in, signed-cookie sessions, roles, and buyer token verification.
3. **[requests-and-spaces.md](requests-and-spaces.md)** — the request
   lifecycle (the station's core state machine) and everything you can do
   to a provisioned space.
4. **[provisioning.md](provisioning.md)** — how an approved request becomes
   Kubernetes resources: manifest rendering, the labeled bundle, the
   status-aware wait, and teardown.
5. **[credits.md](credits.md)** — the money: the shared wallet, payment
   gateways, the buyer purchase flow, the space debit hot path, and
   member earnings.
6. **[deployment.md](deployment.md)** — the Helm chart, the dev loops, TLS,
   and the release pipeline.
7. **[security.md](security.md)** — deployment security guidelines: what
   the admin must ensure around firewalls, DNS, certificates, and secrets
   at rest, with a worked example.

## Terminology (important)

- **"Syft Station"** is the brand — user-visible copy, docs, URLs.
- **`cluster`** is the *integration surface* — every name syft-space or a
  Kubernetes Secret sees keeps it: `SYFT_CLUSTER_CREDITS_*`,
  `SYFT_CLUSTER_MANAGED_BY`, `WalletType.CLUSTER`. Never rename these to
  "station", and never write "cluster" in new user-visible station copy.
- The Kubernetes substrate is always spelled out as "the Kubernetes
  cluster".

## The one contract that must never break

The station and syft-space share **zero code**. The entire contract is:

1. the syft-space **container image** (any published tag),
2. the **`SYFT_*` environment variables** the station injects into each
   space's Secret,
3. the space's **health endpoint** (`/api/v1/health`).

The station backend never imports `syft_space`; where the two sides need a
shape in common, each declares its own (Protocols on the station side).

## Diagrams

The README's images render from mermaid sources in
[`assets/`](assets/) (`*.mmd`). To regenerate a PNG after editing a
source:

```bash
cd station/docs/assets
b64=$(python3 -c 'import json; print(json.dumps({"code": open("architecture.mmd").read(), "mermaid": {"theme": "base"}}))' \
  | base64 | tr '+/' '-_' | tr -d '\n')
curl -sf -o architecture.png "https://mermaid.ink/img/$b64?type=png&bgColor=ffffff&width=1400"
```

Diagrams inside these docs pages are inline mermaid — GitHub renders them
natively, so they need no image files.
