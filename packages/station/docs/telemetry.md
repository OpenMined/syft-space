# Telemetry

OpenTelemetry traces from the station and every space on it, sent to a
backend you choose. Off by default.

What a space records, and what it never records, is described in the Space's
own [telemetry doc](../../spaces/backend/docs/telemetry.md). This page covers
the station side.

## How it works

```
space pods ──┐
             ├─ OTLP/HTTP :4318 ─► OpenTelemetry Collector ──► your backend
station pod ─┘                     (one pod, in the chart)     (SigNoz, Jaeger, Grafana, …)
```

With `telemetry.enabled: true` the chart adds:

- **A Collector** (Deployment + Service `otel-collector`). It receives the
  spaces' traces and forwards them to `telemetry.export.endpoint`. It holds
  the backend's credentials, so spaces never see them.
- **A ConfigMap, `syft-space-telemetry`**, with `OTEL_EXPORTER_OTLP_ENDPOINT`
  (the Collector).

Every space pod loads that ConfigMap through an optional `envFrom`. With the
ConfigMap absent the variables are unset and the space does not trace. The
station server takes no part in that and has no setting for it.

The station pod gets the same Collector address as plain env, and traces
itself as the service `syft-station`.

Storage and the trace viewer are not in the chart. Run them elsewhere, or use
a hosted backend.

## Turning it on

```yaml
telemetry:
  enabled: true
  export:
    endpoint: https://ingest.eu.signoz.cloud:443
    headersSecret: telemetry-backend
    headers:
      signoz-ingestion-key: ingestion-key   # header name: key in the Secret
```

Create the Secret first, in the station's namespace:

```bash
kubectl -n <namespace> create secret generic telemetry-backend \
  --from-literal=ingestion-key=<your key>
```

| Value | Meaning |
|---|---|
| `telemetry.export.endpoint` | Required. Base URL for `http`, `host:port` for `grpc` |
| `telemetry.export.protocol` | `http` (OTLP/HTTP, default) or `grpc` |
| `telemetry.export.insecure` | `grpc` only: send without TLS, for an in-cluster backend |
| `telemetry.export.headersSecret`, `headers` | Request headers whose values live in a Secret |

Any backend that accepts OTLP works; only these values change.

## Telling spaces apart

Each space is its own service, named `ss-<subdomain>`: the space at
`alpha.<domain>` appears as the service `ss-alpha`. All spaces also carry
`service.namespace=syft-space`, to group or filter them together.

## What the station records

| Span | What it covers |
|---|---|
| `POST /api/v1/credits/debit` and other routes | The whole request: route, status, duration |
| `space.provision` | Applying a space's bundle and waiting for it to become available |
| `GET`, `POST`, … (client) | Every outbound HTTP call made with httpx: SyftHub, the image registry, payment gateways |
| `SELECT`, `INSERT`, … | Every SQL statement |

| Attribute | On | Value |
|---|---|---|
| `syft.space.id` | Every span of a space-facing credits request (debit, refund, balance) | The calling space's id in the station database |
| `syft.space.subdomain` | `space.provision` | The space's subdomain |

A space sends trace headers with its credits calls, so the station's spans
for a debit appear inside the space's own query trace.

Not recorded: request and response bodies, tokens, emails, and URL query
strings (they carry emails, as in `/credits/balance?user_email=`). A failed
span keeps only the error's class name. Calls to the Kubernetes API are not
traced; their time shows only as the length of `space.provision`.

The station has no telemetry setting of its own: like a space, it traces when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set. A station run on the host (`just dev`)
cannot reach the in-cluster Collector; set that variable to the backend
directly. Code: `syft_station/components/shared/telemetry.py`.

## Which spaces send traces

A space reads its environment when its pod starts.

- **Turning telemetry on or off:** restart each space (or wait for its next
  restart) for the change to reach it.
- **Spaces provisioned before this feature:** their Deployment has no
  `envFrom` yet. They gain it the next time the station re-renders their
  bundle: a version update, a retry, or a wallet attach.

## Who sees what

Whoever can read the backend sees request timing and load for every space on
the station. Spans carry no query text, responses, emails or tokens.

With `networkPolicy.enabled`, only the space pods and the station pod may
send to the Collector.
