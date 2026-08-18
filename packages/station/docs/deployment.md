# Deployment

One Helm chart (`chart/`) is the source of truth for **every** deployment
— production and dev are the same chart with different values. Nothing
about the shape differs; only `values-dev.yaml` does (ephemeral ChromaDB,
locally-built `:dev` image, `*.localhost` hosts, no NetworkPolicy/TLS).

## What the chart deploys

- **The station pod** — one Deployment (`strategy: Recreate`; SQLite on an
  RWO volume must never have two writers), its Service, Ingress,
  ServiceAccount + namespace-scoped Role
  ([provisioning.md](provisioning.md#rbac)), a PVC for the database, and
  an env Secret.
- **Shared backends** — ChromaDB (one instance; one Chroma *database* per
  space) and docling-serve (document conversion), both digest-pinned.
- **NetworkPolicy** restricting the shared backends to space pods
  (requires a policy-enforcing CNI; k3d's flannel doesn't, so dev leaves
  it off).

Per-space resources are *not* templated in the chart — the station renders
them at runtime ([provisioning.md](provisioning.md)). The chart passes the
per-space defaults to the station as `SYFT_STATION_*` env, mapped
one-to-one from `values.yaml` keys.

Two details that make `helm upgrade` safe:

- The **session secret** is generated on first install and preserved
  across upgrades via a live `lookup` — cookies survive redeploys.
- The station host (`station.ingress.host`) is the single source for the
  station's public URL *and* the base spaces hang off; onboarding shows
  it rather than asking the admin to retype it.

## TLS

Bring-your-own cert. A certificate wildcard matches exactly one label and
never the bare host, so one cert needs **two SANs**: the station host plus
the space wildcard (`*.<host>`, or `*.<prefix>.<host>` if setup picks a
subdomain prefix — the recommended layout, since it confines
member-chosen names to their own subtree). Create it as a
`kubernetes.io/tls` Secret, then:

- `station.ingress.tls.secretName` — the station's own Ingress.
- `spaces.tlsSecret` — what space Ingresses terminate with. **Left empty
  it inherits the station's Secret** (the shared-cert setup is zero extra
  config); set it only when spaces need their own cert. Neither set ⇒
  spaces stay plain http.

`spaces.scheme` is deliberately independent of the cert knobs: TLS may
terminate upstream (a fronting proxy/CDN) with no in-cluster cert at all.
The setup dialog footnotes the exact SANs the cert must cover, derived
live from the chosen prefix.

## The dev loops

Driven by the `justfile`, both on a k3d cluster (prod parity with the k3s
install story):

```bash
just cluster                    # k3d + shared deps only
just dev up admin=you@org.com   # station on the HOST (uvicorn --reload),
                                #   spaces provisioned into k3d via kubeconfig
just up  admin=you@org.com      # FULL in-cluster: the station pod via Helm
just pause                      # stop the cluster; volumes/images survive
just down                       # tear the cluster down (host state kept)
just dev down                   # ...plus wipe host state (~/.syft-station)
```

`just dev` is the everyday loop — uvicorn reloads on edit, no image
rebuild; the chart's dev **host-route** (an ExternalName Service +
Ingress) makes `http://station.localhost` reach the host process through
Traefik, so dev uses the same URLs and onboarding as prod. `just up` is
the parity check. Highlights (the justfile documents the rest):

- Spaces resolve at `<subdomain>.station.localhost` (`*.localhost` →
  loopback in browsers, no DNS setup).
- `syfthub.localhost` is the one canonical name for a host-run local hub:
  `cluster-dns` (CoreDNS rewrite) maps it to the host machine *inside*
  the cluster, so the same hub URL works in browsers, host processes, and
  pods. Never use `host.k3d.internal` or plain `localhost`.
- Both loops self-seed the syft-space `:dev` image (built + imported only
  when missing) and can mount the host's home into spaces read-only at
  `~/host-home` (`spaces.hostMount`, on in values-dev — the k3d cluster
  maps `$HOME` to the node at creation, so recreate the cluster after
  enabling it).

## The release pipeline

`.github/workflows/station-release.yml` — one button, one version,
everything in lockstep:

```
Actions → "Station Release" → Run workflow → patch / minor / major
  release   uv version --bump on station/backend/pyproject.toml,
            commit to main, tag station-<v>   (a record, not a trigger)
  build     multi-arch image (amd64 + arm64), frontend compiled in-image
  manifest  stitch ghcr.io/openmined/syft-station:<v> and :latest
  chart     helm package --version <v> --app-version <v> → push to
            oci://ghcr.io/openmined/charts/syft-station
```

Design notes:

- **`pyproject.toml` is the version's single source** — it's what the
  running station reports at `/version`. The workflow bumps it, so git
  history, the image tag, the chart version, and the live `/version` all
  tell the same number. The repo's `Chart.yaml` stays a placeholder;
  `helm package` stamps it at package time.
- **Everything is one workflow** because a tag pushed with the default
  `GITHUB_TOKEN` cannot trigger another workflow (GitHub's recursion
  guard). Sequential jobs also mean a failed publish is fixed by
  **re-running the failed job** under the same version — never
  re-bumping. A release abandoned instead of re-run leaves a version
  number with no published artifacts; that's normal (versions are
  immutable names, not a counter), and `helm upgrade` never cares about
  gaps.
- User-visible artifacts appear late: `:<v>` and `:latest` only exist
  once the manifest job stitches them, and the chart publishes after the
  image — nobody can install a chart pointing at an image that isn't
  there.
- No secrets to configure: every credential is the run's own
  `GITHUB_TOKEN`, scoped by per-job `permissions:` blocks
  (`contents: write` to push the bump; `packages: write` to publish).

Installing what it published:

```bash
helm install syft-station oci://ghcr.io/openmined/charts/syft-station \
  --version <v> --namespace syft-spaces --create-namespace \
  --set station.adminEmail=... --set station.ingress.host=...
```

The chart's image tag defaults to `appVersion`, so chart `<v>` always
deploys image `<v>`.
