"""Tracing is off by default, and what it records carries nothing private."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from syft_station.components.credits.handlers import AuthedSpace
from syft_station.components.credits.routes import build_credits_routes
from syft_station.components.shared import telemetry
from syft_station.components.shared.telemetry import (
    ENDPOINT_ENV_VARS,
    SPACE_ID_ATTR,
    SPACE_SUBDOMAIN_ATTR,
    flush_telemetry,
    setup_telemetry,
    shutdown_telemetry,
    span,
)
from syft_station.components.spaces.provisioning import SpaceConverger

SPACE_ID = uuid4()


@pytest.fixture(autouse=True)
def no_otlp_endpoint(monkeypatch):
    for name in ENDPOINT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class FakeCreditsHandler:
    """Authenticates every token as one space; a balance read runs one query."""

    def __init__(self, engine):
        self.engine = engine

    async def authenticate(self, token: str) -> AuthedSpace:
        return AuthedSpace(space_id=SPACE_ID, wallet_id=uuid4(), currency="USD")

    async def balance(self, caller: AuthedSpace, user_email: str) -> dict:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"balance": 0, "currency": caller.currency}


@pytest.fixture
async def tracing():
    """A traced app with the credits routes; yields (app, exporter)."""
    exporter = InMemorySpanExporter()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = FastAPI()
    app.include_router(
        build_credits_routes(FakeCreditsHandler(engine), None, None, None, None)
    )

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    setup_telemetry(app, [engine], exporter=exporter)
    yield app, exporter
    shutdown_telemetry()
    await engine.dispose()


def finished(exporter: InMemorySpanExporter) -> dict[str, object]:
    flush_telemetry()
    return {s.name: s for s in exporter.get_finished_spans()}


async def call(app: FastAPI, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://st") as c:
        return await c.get(path, **kwargs)


# ── off by default ──────────────────────────────────────────────────────


def test_setup_does_nothing_without_an_endpoint():
    app = FastAPI()

    setup_telemetry(app, [])

    assert telemetry._provider is None
    assert app.user_middleware == []


def test_spans_are_harmless_when_tracing_is_off():
    with span("space.provision") as current:
        pass

    assert not current.is_recording()


@pytest.mark.parametrize("name", ENDPOINT_ENV_VARS)
def test_an_otlp_endpoint_turns_tracing_on(monkeypatch, name):
    monkeypatch.setenv(name, "http://collector:4318")

    assert telemetry.telemetry_enabled()


# ── what is recorded ────────────────────────────────────────────────────


async def test_a_credits_request_and_its_sql_carry_the_calling_space(tracing):
    app, exporter = tracing

    response = await call(
        app,
        "/credits/balance?user_email=buyer@test.com",
        headers={"Authorization": "Bearer sct_secret"},
    )

    assert response.status_code == 200
    spans = finished(exporter)
    request = spans["GET /credits/balance"]
    sql = next(s for name, s in spans.items() if name.startswith("SELECT"))
    assert sql.parent.span_id == request.context.span_id
    assert request.attributes[SPACE_ID_ATTR] == str(SPACE_ID)
    assert sql.attributes[SPACE_ID_ATTR] == str(SPACE_ID)


async def test_the_health_probe_is_not_traced(tracing):
    app, exporter = tracing

    await call(app, "/healthz")

    assert finished(exporter) == {}


async def test_a_request_joins_the_trace_of_the_space_that_called(tracing):
    app, exporter = tracing
    trace_id = "0af7651916cd43dd8448eb211c80319c"

    await call(
        app,
        "/credits/balance?user_email=buyer@test.com",
        headers={
            "Authorization": "Bearer sct_secret",
            "traceparent": f"00-{trace_id}-b7ad6b7169203331-01",
        },
    )

    request = finished(exporter)["GET /credits/balance"]
    assert format(request.context.trace_id, "032x") == trace_id


async def test_provisioning_is_one_span_named_for_the_space(tracing):
    _, exporter = tracing
    space = SimpleNamespace(
        id=uuid4(),
        subdomain="alpha",
        name="Alpha",
        owner_email="owner@test.com",
        wallet_id=None,
        url="",
        version="",
    )

    class Repo:
        async def get_token(self, space_id):
            return None

        async def update(self, space):
            return space

        async def clear_conditions(self, space_id, types):
            return None

    class Setup:
        async def get_config(self):
            return SimpleNamespace(supported_version="1.0.0", domain="st.test")

    class Provisioner:
        async def provision(self, spec):
            return "https://alpha.st.test"

    converger = SpaceConverger(Repo(), Setup(), Provisioner(), credits=None)

    assert await converger.converge(space) == "https://alpha.st.test"
    provision = finished(exporter)["space.provision"]
    assert provision.attributes[SPACE_SUBDOMAIN_ATTR] == "alpha"


# ── nothing private ─────────────────────────────────────────────────────


async def test_a_failed_span_keeps_the_error_class_but_not_its_message(tracing):
    _, exporter = tracing

    with pytest.raises(ValueError), span("space.provision"):
        raise ValueError("owner@test.com could not be provisioned")

    failed = finished(exporter)["space.provision"]
    assert failed.status.status_code == StatusCode.ERROR
    assert failed.status.description == "ValueError"
    assert failed.events == ()


async def test_the_token_and_the_buyer_email_in_the_url_are_not_recorded(tracing):
    app, exporter = tracing

    await call(
        app,
        "/credits/balance?user_email=buyer@test.com",
        headers={"Authorization": "Bearer sct_secret"},
    )

    spans = finished(exporter)
    assert (
        spans["GET /credits/balance"]
        .attributes["http.url"]
        .endswith("/credits/balance")
    )
    for recorded in spans.values():
        values = " ".join(str(v) for v in recorded.attributes.values())
        assert "sct_secret" not in values
        assert "buyer@test.com" not in values


async def test_an_outbound_call_is_recorded_without_its_query_string(tracing):
    _, exporter = tracing
    server = await asyncio.start_server(_answer_ok, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async with server, httpx.AsyncClient() as client:
        await client.get(f"http://127.0.0.1:{port}/verify?email=buyer@test.com")

    outbound = finished(exporter)["GET"]
    assert outbound.attributes["http.url"] == f"http://127.0.0.1:{port}/verify"


async def _answer_ok(reader, writer) -> None:
    await reader.readuntil(b"\r\n\r\n")
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
    await writer.drain()
    writer.close()
