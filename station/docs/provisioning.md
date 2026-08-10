# Provisioning

How an approved request becomes Kubernetes resources. The `provision/`
component has no routes — it's the substrate layer the requests and spaces
components drive.

## The Provisioner protocol

`provision/interfaces.py` defines `Provisioner` (provision, teardown,
scale, patch-secret, status) plus the value objects: `SpaceSpec` (what to
deploy: subdomain, owner, version, domain, admin token, credits grant) and
`SpaceRuntimeStatus` (what's live). Two implementations, chosen by
`SYFT_STATION_PROVISIONER`:

- **`MockProvisioner`** (default) — no cluster needed; instant success,
  except a subdomain containing `fail` provisions to FAILED, so the retry
  path is exercisable from the UI in host-only dev.
- **`K8sProvisioner`** (`provision/k8s.py`) — the real one. The
  `kubernetes` client is synchronous, so every call goes through
  `asyncio.to_thread`; the station's event loop never blocks on the
  API server. In-cluster it authenticates as the chart's ServiceAccount;
  off-cluster (the `just dev` loop) it uses kubeconfig.

## Manifest rendering

`provision/manifests.py` renders the per-space bundle from **real YAML
templates** (`syft_station/k8s/space/*.yaml`) with `${VAR}` placeholders —
reviewable manifests that read like `kubectl get -o yaml` output, filled
by a plain `string.Template` substitution. Every substituted value is a
scalar; the env-var set is fixed.

Anything **conditional is injected in Python**, not templated — the
templates stay valid YAML with no control flow:

| Injection | Condition | Effect |
|---|---|---|
| Credits keys | space has a wallet grant | `SYFT_CLUSTER_CREDITS_URL/TOKEN/CURRENCY/WALLET_ID`, `SYFT_CLUSTER_PUBLIC_URL` (+ optional `WALLET_OWNER`, `BUNDLES`) added to the Secret; the Deployment reads them via optional `secretKeyRef`s, so absent keys just leave env unset |
| Host mount | `space_host_mount` | node's `/mnt/host-home` mounted read-only at `/root/host-home` — *inside* the container's home, because syft-space's dataset file browser is rooted at home and rejects paths outside it. `DirectoryOrCreate` so an unmapped node serves an empty dir instead of wedging the pod |
| TLS | `space_tls_secret` | a `tls:` section on the Ingress pointing at the shared wildcard cert Secret ([deployment.md](deployment.md#tls)) |

## The bundle

Five resources per space, applied in dependency order (Secret + PVC before
the Deployment that mounts them; Service before Ingress), all labeled
`syftcluster.openmined.org/space: <subdomain>` — the label selects the
whole bundle for status, teardown, and convergence:

```
Secret      env for the space: admin token, ChromaDB/docling endpoints,
            managed-by, public URL, credits keys (conditional)
PVC         the space's data volume (survives update/restart/pause)
Deployment  the syft-space container, resources from station config
Service     port 80 → the space
Ingress     <subdomain>.<domain> → Service (TLS section conditional)
```

Provisioning is **convergent**: create-or-patch per resource, PVC kept.
Re-running it on an existing space is an update, not an error — that's
what makes retry, version updates, and wallet rollout all the same code
path (the `SpaceConverger`, [requests-and-spaces.md](requests-and-spaces.md#the-converger)).

## The status-aware wait

After applying, the provisioner polls the Deployment until it reports an
available replica — but a bare timeout would burn minutes on hopeless
pods and fail slow ones prematurely, so the wait inspects the space's
pods each tick:

- **Fail fast** on terminal states (`_FATAL_WAITING_REASONS`: provably
  invalid config, states the kubelet has given up retrying).
  `ErrImagePull` is deliberately *not* fatal — a registry blip gets
  natural grace until the kubelet escalates it to `ImagePullBackOff`.
- **Extend the deadline** (capped) while there's visible startup
  progress, so a slow image pull isn't misreported as failure.
- On crash loops, the container's log tail is fetched (best-effort) so
  the failure reason shown to the admin says *why*.

This wait is why the chart's Role grants `pods list` and `pods/log get`
in addition to Deployment access — trimming those grants makes the first
provision 403 while a retry appears to "heal" (the Deployment is
available by then, so the pod inspection is never reached).

## Runtime status

`GET /spaces/{id}/status` and the spaces list derive status live from the
Deployment (`deployments/status` + the same pod inspection): running,
starting, failed (with reason), paused (scaled to 0), or gone. Nothing
runtime is persisted — see the design note in
[architecture.md](architecture.md).

## Teardown

Deletes the bundle in reverse order. The PVC is kept unless `purge=True`
— pausing or deleting a misbehaving space doesn't destroy member data
unless the admin explicitly purges it.

## RBAC

The chart's Role (`chart/templates/station/rbac.yaml`) grants exactly
what the provisioner calls, namespace-scoped, never cluster-admin:
Secret/Service/PVC/Deployment get-create-patch-delete,
`deployments/status` get, `deployments/scale` get-patch (pause/resume),
`pods` list + `pods/log` get (the wait), and Ingress
get-create-patch-delete. Verify changes with
`kubectl auth can-i --as=system:serviceaccount:syft-spaces:syft-station`.
