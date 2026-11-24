# Telemetry

Syft Space can emit [OpenTelemetry](https://opentelemetry.io) traces: where the
time goes inside each request. It is **off by default** and sends nothing
unless you point it at a collector.

The Space only emits. Collecting, storing and viewing the data is done by a
separate server that you run (Jaeger, SigNoz, Grafana, or any other that
accepts OTLP).

## Turn it on

Set the collector's address before starting the backend:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
packages/spaces/run.sh
```

| Variable | Purpose | Default |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector address, OTLP over HTTP. Unset or empty means off | off |
| `OTEL_SERVICE_NAME` | Name shown in the viewer | `syft-space` |
| `OTEL_EXPORTER_OTLP_HEADERS` | Extra headers, for example an ingestion key | none |
| `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG` | Sampling, for example `traceidratio` and `0.1` | every request |

With Docker Compose, set the same variables in your shell or `.env`. A
collector on the host is reached at `http://host.docker.internal:4318`. To run
a viewer in Compose as well, see the next section.

## A viewer for local use

Jaeger runs as one container and is enough to look at traces. It keeps them
in memory, so they are lost when it stops.

**With Docker Compose**, add the telemetry overlay. It starts Jaeger next to
the Space and points the Space at it:

```bash
cd packages/spaces
docker compose -f docker-compose.yml -f docker-compose.telemetry.yml up --build
```

**Without Compose**, start Jaeger yourself and set the endpoint as shown above:

```bash
docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/jaeger:2.14.0
```

Either way, open <http://localhost:16686> and pick the `syft-space` service.

For load tests, or to keep traces, send them to a collector on a different
machine (SigNoz, Grafana, or another OTLP backend), so it does not compete
with the Space for CPU and disk.

## What is recorded

| Span | Covers |
|---|---|
| `POST /api/v1/endpoints/{slug}/query` and other routes | The whole request: route, status, duration |
| `auth.verify_sender` | Verifying the caller's satellite token |
| `query.policy.pre` | Policy checks before the query |
| `query.search` | Dataset search |
| `query.chat` | Model call |
| `query.policy.post` | Policy steps after the query |
| `GET`, `POST`, … (client) | Every outbound HTTP call made with httpx, including calls to SyftHub |
| `SELECT`, `INSERT`, … | Every SQL statement, on both databases |

Attributes added by the Space:

| Attribute | On | Value |
|---|---|---|
| `syft.endpoint.slug` | Every span of a query, including its SQL and outbound HTTP spans | Slug of the Syft Space endpoint queried, for example `my-docs` |
| `syft.query.outcome` | The request span | `success`, `payment_required`, … |
| `syft.dataset.type` | `query.search` | For example `chroma` |
| `syft.model.type` | `query.chat` | For example `openai` |

"Endpoint" here means a Syft Space endpoint (a dataset and/or model you
publish), not an HTTP route. The route is recorded separately on the request
span as `http.route`, and is the same for every Space endpoint.

## What is not recorded

- Query text, responses, emails, tokens and request bodies.
- Error messages: a failed span keeps only the error's class name.

Request URLs and SQL statement text are recorded. SQL values are not, since
statements use placeholders.

## Code

`syft_space/components/shared/telemetry.py`.

Time a step by decorating the async function that does it:

```python
from syft_space.components.shared.telemetry import traced

@traced("query.rerank")
async def _rerank(self, documents): ...
```

Use `with span("name"):` when the step is only part of a function.

Attributes that belong to the whole request are set once, and reach every
span started after that point:

```python
set_request_attributes(endpoint_slug=slug)
```
