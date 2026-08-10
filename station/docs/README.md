# Syft Station — implementation docs

Documentation of how the station is built, one page per area. The audience
is someone working on the code; for what the station *is* and how to run
one, start at the [station README](../README.md).

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
