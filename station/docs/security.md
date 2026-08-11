# Security guidelines for deployment

What the admin must ensure before and after `helm install` — network
exposure, DNS and certificates, secrets at rest, and the in-cluster
boundaries the chart sets up. Everything below uses one worked example:

> **Acme** deploys its station at **`station.acme.org`** and, following the
> recommended layout, puts member spaces under a prefix:
> **`*.spaces.station.acme.org`** (so Alice's space is
> `alice.spaces.station.acme.org`). The prefix confines member-chosen
> subdomains to their own subtree — a member requesting `www` or `api`
> gets `www.spaces.station.acme.org`, never a name beside Acme's real DNS
> estate.

## DNS

Two records, both pointing at the cluster's ingress (the load balancer in
front of Traefik):

| Record | Type | Points to | Serves |
|---|---|---|---|
| `station.acme.org` | A / CNAME | ingress LB | the station UI + API |
| `*.spaces.station.acme.org` | A / CNAME | ingress LB | every member space |

A DNS wildcard matches any depth, so one `*.station.acme.org` record would
also work — it's the **certificate** wildcard that is one-level-strict
(below), which is why the DNS and cert layouts should be chosen together.

## Certificates

A certificate wildcard matches **exactly one label** and **never the bare
host**. So one certificate with two SANs covers everything:

```
station.acme.org                # the station itself
*.spaces.station.acme.org       # every member space
```

(Flat layout — no prefix — needs `station.acme.org` + `*.station.acme.org`
instead. An off-the-shelf `*.acme.org` cert covers **neither** layout's
space names; issue the cert for the station's own subtree.)

Create it as a standard TLS Secret and point the chart at it — spaces
inherit the station's Secret when `spaces.tlsSecret` is left empty:

```bash
kubectl -n syft-spaces create secret tls station-tls \
  --cert=fullchain.pem --key=privkey.pem

helm upgrade --install syft-station oci://ghcr.io/openmined/charts/syft-station \
  --namespace syft-spaces \
  --set station.adminEmail=admin@acme.org \
  --set station.ingress.host=station.acme.org \
  --set station.ingress.tls.enabled=true \
  --set station.ingress.tls.secretName=station-tls
```

During first-run setup, enter `spaces` as the subdomain prefix — the setup
dialog footnotes the exact SANs your certificate must cover, derived from
what you type.

**Renewal** is the admin's job (the chart is bring-your-own-cert by
design): replace the Secret's contents and Traefik picks it up — no
restarts. If you automate issuance with cert-manager installed separately,
point its Certificate at the same Secret name.

**Cookie hardening — do not skip.** The chart does not currently derive
this from the TLS setting, so behind HTTPS explicitly set:

```bash
  --set station.extraEnv.SYFT_STATION_SESSION_COOKIE_SECURE=true
```

This marks the session cookie `Secure` and upgrades its name to
`__Host-…`, which browsers bind to the exact host — a space on a sibling
subdomain then **cannot read, set, or shadow the station's admin session**.
Without it, the signed payload still prevents forgery, but the
subdomain-isolation guarantee is weaker. ([auth.md](auth.md) has the
mechanism.)

## Firewall: what must be reachable

### Inbound — exactly one door

| Port | To | Why |
|---|---|---|
| 443 | ingress LB | station UI/API, all spaces, payment webhooks |
| 80 | ingress LB | optional — only for HTTP→HTTPS redirect |

Everything else stays closed. In particular:

- **The Kubernetes API (6443) must not be internet-reachable.** The
  station talks to it from inside the cluster.
- **ChromaDB and docling-serve have no Ingress** — they are
  ClusterIP-only, as is the station's own Service (8090). Nothing in the
  chart exposes a port besides the ingress; keep it that way.
- **Payment webhooks ride the same 443**: Xendit and Stripe deliver to
  `https://station.acme.org/api/v1/credits/webhooks/{provider}`, so the
  station host must be reachable from the providers' networks. Do not
  try to IP-allowlist providers as the primary control — the real
  protection is that every webhook is **signature-verified** (Stripe
  HMAC with a tolerance window; Xendit callback token) before it can
  move money. An unverified request is rejected regardless of source.

### Outbound — the egress allowlist

For a strict egress-filtered environment, the station pod needs:

| Destination | Port | Why |
|---|---|---|
| `syfthub.openmined.org` (or your own hub) | 443 | member sign-in, buyer token verification |
| `api.xendit.co` / `api.stripe.com` | 443 | checkout-session creation (only the configured provider) |
| `ghcr.io` + `*.githubusercontent.com` | 443 | image pulls and the version picker's tag listing (GHCR redirects blob downloads to githubusercontent) |

Space pods additionally reach SyftHub (publishing endpoints) and
**whatever AI model providers their owners configure** (OpenAI,
Anthropic, a self-hosted vLLM, …) — spaces cannot be egress-pinned by the
station; scope their allowance per your members' needs or accept broad
443 egress from the spaces namespace.

## Secrets at rest

Know where the sensitive material lives, because it defines what a backup
or a compromised volume exposes:

- **The station's SQLite database** (`/data/app.db` on the station PVC)
  holds the wallet's **payment-provider credentials** (API key, webhook
  secret), the **SyftHub PAT**, and the spaces' **admin tokens** in
  plaintext, plus hashed space-credits tokens. Treat the PVC and any
  backup of it like a credentials store: encrypt backups, restrict who
  can `kubectl exec` into the namespace or read its PVCs.
- **The session signing key** lives in a chart-managed Secret and is
  preserved across `helm upgrade`. Anyone who can read Secrets in the
  namespace can mint admin sessions — namespace RBAC on the Kubernetes
  side is the actual admin-access boundary.
- **Per-space Secrets** carry that space's admin token and credits token.
  Every re-provision mints fresh ones ([credits.md](credits.md)); a
  leaked token is invalidated by re-provisioning the space or
  regenerating its key.
- The station stores **no member passwords, ever** — sign-in is a
  one-shot SyftHub proxy and hub tokens are discarded
  ([auth.md](auth.md)).

## What the cluster enforces

Already in the chart, worth knowing when you review it:

- **RBAC**: the station's ServiceAccount gets a namespace-scoped Role
  covering exactly what the provisioner does — never cluster-admin
  ([provisioning.md](provisioning.md#rbac)).
- **NetworkPolicy** (`networkPolicy.enabled`, on by default): only pods
  carrying the space label may reach ChromaDB and docling-serve. It
  requires a **policy-enforcing CNI** — on plain k3s/flannel the policy
  is accepted but silently unenforced, so if backend isolation matters
  to you, run Calico/Cilium or verify your CNI enforces it.
- **One admin, by config**: the admin role is granted solely by
  `station.adminEmail` matching at sign-in. Rotating the admin =
  changing the value and re-deploying; there is no in-band privilege
  escalation path.

## Pre-flight checklist

- [ ] DNS: station host + space wildcard → ingress LB
- [ ] Cert with both SANs, created as a `kubernetes.io/tls` Secret
- [ ] `station.ingress.tls.enabled=true` + `secretName` set
- [ ] `SYFT_STATION_SESSION_COOKIE_SECURE=true` via `station.extraEnv`
- [ ] Inbound firewall: 443 (and optionally 80) to the LB, nothing else
- [ ] Kubernetes API not internet-reachable
- [ ] Egress allowlist covers hub, payment provider, GHCR (if filtering)
- [ ] PVC backups treated as secret material
- [ ] CNI actually enforces NetworkPolicy (or accept backend exposure inside the cluster)
- [ ] `station.adminEmail` is a real SyftHub account you control
