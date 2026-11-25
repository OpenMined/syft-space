# Telemetry

OpenTelemetry traces from every space on the station, sent to a backend you
choose. Off by default.

What a space records, and what it never records, is described in the Space's
own [telemetry doc](../../spaces/backend/docs/telemetry.md). This page covers
the station side only.

## How it works

```
space pods ── OTLP/HTTP :4318 ──► OpenTelemetry Collector ──► your backend
                                  (one pod, in the chart)     (SigNoz, Jaeger, Grafana, …)
```

With `telemetry.enabled: true` the chart adds:

- **A Collector** (Deployment + Service `otel-collector`). It receives the
  spaces' traces and forwards them to `telemetry.export.endpoint`. It holds
  the backend's credentials, so spaces never see them.
- **A ConfigMap, `syft-space-telemetry`**, with `OTEL_EXPORTER_OTLP_ENDPOINT`
  (the Collector) and `OTEL_SERVICE_NAME`.

Every space pod loads that ConfigMap through an optional `envFrom`. With the
ConfigMap absent the variables are unset and the space does not trace. The
station server takes no part in this and has no telemetry setting.

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
| `telemetry.serviceName` | `service.name` on every span; default `syft-space` |

Any backend that accepts OTLP works; only these values change.

## Telling spaces apart

All spaces share one `service.name`. Each pod also sets
`service.instance.id` to its subdomain, so group or filter by that.

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

With `networkPolicy.enabled`, only space pods may send to the Collector.
