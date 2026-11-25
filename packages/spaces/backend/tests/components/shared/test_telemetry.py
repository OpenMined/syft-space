"""Tracing is off by default, and what it records carries nothing private."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from syft_space.components.shared import telemetry
from syft_space.components.shared.telemetry import (
    ENDPOINT_ENV_VARS,
    ENDPOINT_SLUG_ATTR,
    flush_telemetry,
    set_request_attributes,
    set_span_attributes,
    setup_telemetry,
    shutdown_telemetry,
    span,
    traced,
)
from tests.components.endpoints.test_response_type_flow import (
    TENANT_ID,
    _make_endpoint,
    _make_handler,
    _make_request,
)


@pytest.fixture(autouse=True)
def no_otlp_endpoint(monkeypatch):
    for name in ENDPOINT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
async def tracing():
    """A traced app with one route and one database; yields (app, exporter)."""
    exporter = InMemorySpanExporter()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = FastAPI()

    @traced("query.search")
    async def search():
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    @app.get("/endpoints/{slug}/query")
    async def query(slug: str):
        set_request_attributes(endpoint_slug=slug)
        await search()
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    # The real app runs requests through this kind of middleware.
    @app.middleware("http")
    async def passthrough(request, call_next):
        return await call_next(request)

    setup_telemetry(app, [engine], exporter=exporter)
    yield app, exporter
    shutdown_telemetry()
    await engine.dispose()


def exporter_spans(exporter: InMemorySpanExporter) -> tuple:
    flush_telemetry()
    return exporter.get_finished_spans()


def finished(exporter: InMemorySpanExporter) -> dict[str, object]:
    return {s.name: s for s in exporter_spans(exporter)}


async def call(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://space") as c:
        return await c.get(path)


# ── off by default ──────────────────────────────────────────────────────


def test_setup_does_nothing_without_an_endpoint():
    app = FastAPI()

    setup_telemetry(app, [])

    assert telemetry._provider is None
    assert app.user_middleware == []


def test_spans_are_harmless_when_tracing_is_off():
    with span("query.search", **{ENDPOINT_SLUG_ATTR: "ep"}) as current:
        set_span_attributes(**{"syft.dataset.type": "chroma"})

    assert not current.is_recording()


@pytest.mark.parametrize("name", ENDPOINT_ENV_VARS)
def test_an_otlp_endpoint_turns_tracing_on(monkeypatch, name):
    monkeypatch.setenv(name, "http://collector:4318")

    assert telemetry.telemetry_enabled()


# ── what a request records ──────────────────────────────────────────────


async def test_a_request_records_its_route_step_and_sql_in_one_trace(tracing):
    app, exporter = tracing

    await call(app, "/endpoints/ep/query")

    spans = finished(exporter)
    request = spans["GET /endpoints/{slug}/query"]
    step = spans["query.search"]
    sql = next(s for name, s in spans.items() if name.startswith("SELECT"))
    assert step.parent.span_id == request.context.span_id
    assert sql.parent.span_id == step.context.span_id


async def test_request_attributes_reach_every_span_of_that_request_only(tracing):
    app, exporter = tracing

    await call(app, "/endpoints/first/query")
    await call(app, "/endpoints/second/query")

    slugs_by_trace: dict[int, set[str]] = {}
    for recorded in exporter_spans(exporter):
        slugs = slugs_by_trace.setdefault(recorded.context.trace_id, set())
        slugs.add(recorded.attributes[ENDPOINT_SLUG_ATTR])
    # Every span carries its own request's slug, including the SQL ones.
    assert sorted(slugs_by_trace.values(), key=sorted) == [{"first"}, {"second"}]


async def test_a_traced_function_keeps_its_name_and_result(tracing):
    @traced("step")
    async def double(value: int) -> int:
        return value * 2

    assert await double(2) == 4
    assert double.__name__ == "double"


async def test_the_health_poll_is_not_traced(tracing):
    app, exporter = tracing

    await call(app, "/health")

    assert finished(exporter) == {}


async def test_outbound_httpx_calls_are_traced(tracing):
    """Against a real socket: only httpx's own transports are instrumented."""
    _, exporter = tracing

    async def respond(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server, httpx.AsyncClient() as client:
        await client.get(f"http://127.0.0.1:{port}/api/v1/verify")

    attributes = dict(finished(exporter)["GET"].attributes)
    url = attributes.get("url.full") or attributes.get("http.url")
    status = attributes.get("http.response.status_code") or attributes.get(
        "http.status_code"
    )
    assert url == f"http://127.0.0.1:{port}/api/v1/verify"
    assert status == 200


# ── nothing private ─────────────────────────────────────────────────────


def test_a_failed_span_keeps_the_error_class_and_drops_the_message(tracing):
    _, exporter = tracing

    with pytest.raises(ValueError):
        with span("query.chat"):
            raise ValueError("user@example.com asked about their diagnosis")

    failed = finished(exporter)["query.chat"]
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.status.description == "ValueError"
    assert failed.events == ()


def test_none_attributes_are_left_out(tracing):
    _, exporter = tracing

    with span(
        "query.search", **{ENDPOINT_SLUG_ATTR: None, "syft.dataset.type": "chroma"}
    ):
        set_span_attributes(**{"syft.model.type": None})

    assert dict(finished(exporter)["query.search"].attributes) == {
        "syft.dataset.type": "chroma"
    }


# ── the query pipeline ──────────────────────────────────────────────────


async def test_a_query_records_one_span_per_step(tracing):
    _, exporter = tracing
    handler, _, _ = _make_handler(_make_endpoint("both"))

    with span("request"):
        await handler.query_endpoint(
            "ep", _make_request(), SimpleNamespace(id=TENANT_ID)
        )

    spans = finished(exporter)
    for step in ("query.policy.pre", "query.search", "query.chat", "query.policy.post"):
        assert spans[step].attributes[ENDPOINT_SLUG_ATTR] == "ep"
    assert spans["query.search"].attributes["syft.dataset.type"] == "chroma"
    assert spans["query.chat"].attributes["syft.model.type"] == "openai"
    assert spans["request"].attributes["syft.query.outcome"] == "success"


async def test_query_spans_hold_no_query_text_or_email(tracing):
    _, exporter = tracing
    handler, _, _ = _make_handler(_make_endpoint("both"))
    request = _make_request()

    await handler.query_endpoint("ep", request, SimpleNamespace(id=TENANT_ID))

    recorded = repr(
        [(s.name, dict(s.attributes)) for s in exporter.get_finished_spans()]
    )
    assert request.messages not in recorded
    assert str(request.sender_email) not in recorded


async def test_a_chromadb_search_times_the_query_embedding(tracing, monkeypatch):
    """The embedding runs in this process and competes with ingestion for CPU."""
    from syft_space.components.shared.search_types import SearchContext
    from syft_space.components.vector_stores.chromadb_local import (
        chromadb_vector_store as store_module,
    )

    _, exporter = tracing
    monkeypatch.setattr(store_module, "_chromadb_available", lambda: True)

    class Collection:
        async def query(self, **kwargs):
            return {
                "ids": [[]],
                "distances": [[]],
                "documents": [[]],
                "metadatas": [[]],
            }

    class Client:
        async def get_collection(self, name):
            return Collection()

    async def get_client():
        return Client()

    store = store_module.ChromaDBLocalVectorStore.__new__(
        store_module.ChromaDBLocalVectorStore
    )
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]
    store.get_client = get_client  # type: ignore[method-assign]
    store.config = SimpleNamespace(collection_name="c")

    with span("query.search"):
        await store.search(
            SearchContext(sender="u@example.org", dataset_id=TENANT_ID), "what is tcp?"
        )

    spans = finished(exporter)
    assert spans["query.embed"].parent.span_id == spans["query.search"].context.span_id
    assert "what is tcp?" not in repr(dict(spans["query.embed"].attributes))
