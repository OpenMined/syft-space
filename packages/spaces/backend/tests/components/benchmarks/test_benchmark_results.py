"""Benchmark results: the runs and their reports, proxied from the benchmark.

Covered: the proxies passing their query and body through, refusals keeping
their status, and the summary document and export arriving with their own name
and type.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from syft_space.components.benchmarks import client as client_module
from syft_space.components.benchmarks.client import BenchmarkClient, Reply
from syft_space.components.benchmarks.entities import (
    BenchmarkConnection,
    BenchmarkTarget,
)
from syft_space.components.benchmarks.handlers import BenchmarkHandler
from syft_space.components.benchmarks.routes import build_benchmark_routes
from syft_space.components.tenants.dependency import get_tenant_dependency

TENANT = SimpleNamespace(id=uuid4(), name="default")
ENDPOINT_ID = uuid4()
SLUG = "support-kb"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_CHUNKS = (b"PK\x03\x04", b"xlsx-" * 1000, b"end")


class _Console:
    """The benchmark's console: answers each route, remembers every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, dict]] = []
        self.runs = [
            {"job_id": "job-new", "created_at": "2026-09-30T03:00:00Z"},
            {"job_id": "job-mid", "created_at": "2026-09-20T03:00:00Z"},
            {"job_id": "job-old", "created_at": "2026-08-01T03:00:00Z"},
        ]

    async def mint_session(self, key: str) -> Reply:
        return Reply(ok=True, data={"token": "t", "expires_at": "2026-10-03T18:00:00Z"})

    async def raw(
        self, method: str, path: str, *, body: object = None, params: dict | None = None
    ) -> Reply:
        params = params or {}
        self.calls.append((method, path, body, params))
        if path == "/console/report/runs":
            items = list(self.runs)
            return Reply(
                ok=True,
                data={
                    "in_progress": [{"job_id": "job-running", "state": "running"}],
                    "items": items,
                    "total": len(items),
                },
            )
        if path.endswith("/fragments"):
            return Reply(ok=True, data=[{"file_name": "a.md", "is_source": True}])
        if method == "DELETE":
            return Reply(ok=True, status=204)
        if path.startswith("/console/report/runs/") and path.count("/") == 4:
            return Reply(
                ok=True,
                data={
                    "run": {"job_id": path.rsplit("/", 1)[1]},
                    "timing": TIMING,
                },
            )
        if path == "/console/report/runs/missing/questions":
            return Reply(ok=False, status=404, detail="there is no job missing")
        return Reply(ok=True, data={"items": [], "total": 0})

    async def download(self, path: str, *, params: dict | None = None) -> Reply:
        self.calls.append(("GET", path, None, params or {}))
        return Reply(
            ok=True,
            data=b"PK\x03\x04docx",
            status=200,
            headers={
                "content-type": DOCX,
                "content-disposition": (
                    'attachment; filename="support-kb-2026-09-30-0300.docx"'
                ),
            },
        )

    async def stream(
        self, path: str, *, params: dict | None = None
    ) -> tuple[Reply, AsyncIterator[bytes] | None]:
        self.calls.append(("GET", path, None, params or {}))
        if "/missing/" in path:
            return Reply(ok=False, status=404, detail="there is no job missing"), None

        async def body() -> AsyncIterator[bytes]:
            for chunk in XLSX_CHUNKS:
                yield chunk

        headers = {
            "content-type": XLSX,
            "content-disposition": (
                'attachment; filename="support-kb-run-2026-09-30-0300.xlsx"'
            ),
        }
        return Reply(ok=True, status=200, headers=headers), body()


def _endpoint() -> SimpleNamespace:
    return SimpleNamespace(
        id=ENDPOINT_ID,
        slug=SLUG,
        name="Support KB",
        dataset_id=None,
        response_type="both",
    )


def _handler() -> tuple[BenchmarkHandler, _Console]:
    console = _Console()
    connection = BenchmarkConnection(
        tenant_id=TENANT.id, name="b", url="http://benchmark:8200", token="k"
    )
    target = BenchmarkTarget(tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID)

    connections = AsyncMock()
    connections.get = AsyncMock(return_value=connection)
    connections.default_for = AsyncMock(return_value=connection)
    targets = AsyncMock()
    targets.for_endpoint = AsyncMock(return_value=target)
    endpoints = AsyncMock()
    endpoints.get_by_slug = AsyncMock(return_value=_endpoint())

    handler = BenchmarkHandler(
        connection_repository=connections,
        target_repository=targets,
        endpoint_repository=endpoints,
        dataset_repository=AsyncMock(),
        dataset_registry=SimpleNamespace(),
    )
    handler._client = lambda connection: console  # type: ignore[method-assign,assignment]
    handler._console_client = lambda connection, token: console  # type: ignore[method-assign,assignment]
    return handler, console


def _app(handler: BenchmarkHandler) -> TestClient:
    app = FastAPI()
    app.include_router(build_benchmark_routes(handler))
    app.dependency_overrides[get_tenant_dependency] = lambda: TENANT
    return TestClient(app)


def _runs_call(console: _Console) -> dict:
    return next(c for c in console.calls if c[1] == "/console/report/runs")[3]


# --- the runs list ----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_runs_list_is_the_benchmarks_own() -> None:
    handler, console = _handler()
    data = await handler.list_report_runs(TENANT, SLUG, {"limit": 25})
    assert [r["job_id"] for r in data["items"]] == ["job-new", "job-mid", "job-old"]
    assert data["in_progress"] == [{"job_id": "job-running", "state": "running"}]
    assert _runs_call(console) == {"limit": 25}


def test_runs_route_passes_dates_and_paging_through() -> None:
    handler, console = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs",
        params={"from": "2026-09-01", "to": "2026-09-30", "limit": 5, "offset": 10},
    )
    assert resp.status_code == 200
    assert _runs_call(console) == {
        "from": "2026-09-01",
        "to": "2026-09-30",
        "limit": 5,
        "offset": 10,
    }


# --- one run ----------------------------------------------------------------

TIMING = {
    "total_s": 10.0,
    "phases": [{"phase": "evaluate", "s": 9.5}],
    "passes": [],
    "calls": [],
    "concurrency": {"model": 16, "endpoint": 2},
}


@pytest.mark.asyncio
async def test_a_runs_report_is_passed_through() -> None:
    handler, console = _handler()
    data = await handler.get_report_run(TENANT, SLUG, "job-mid")
    assert console.calls[-1][1] == "/console/report/runs/job-mid"
    assert data == {"run": {"job_id": "job-mid"}, "timing": TIMING}


def test_questions_route_passes_every_query_parameter_through() -> None:
    handler, console = _handler()
    query = {
        "model": "m1",
        "group": "fixed",
        "generator": "mcq",
        "q": "tax",
        "limit": "10",
        "offset": "20",
    }
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/questions", params=query
    )
    assert resp.status_code == 200
    method, path, _, params = console.calls[-1]
    assert (method, path) == ("GET", "/console/report/runs/job-mid/questions")
    assert params == query


@pytest.mark.parametrize(
    ("part", "query"),
    [
        ("filter", {"stage": "web_check", "outcome": "removed", "limit": "10"}),
        ("generated", {"generator": "mcq", "status": "active", "offset": "5"}),
    ],
)
def test_filter_and_generated_pass_the_query_through(
    part: str, query: dict[str, str]
) -> None:
    handler, console = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/{part}", params=query
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}
    method, path, _, params = console.calls[-1]
    assert (method, path) == ("GET", f"/console/report/runs/job-mid/{part}")
    assert params == query


def test_a_benchmark_refusal_keeps_its_status() -> None:
    handler, _ = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/missing/questions",
        params={"model": "m1"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "there is no job missing"


def test_question_detail_and_fragments_are_proxied_with_the_model() -> None:
    handler, console = _handler()
    client = _app(handler)
    base = f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/questions/qa-7"
    assert client.get(base, params={"model": "m1"}).status_code == 200
    assert console.calls[-1][1:] == (
        "/console/report/runs/job-mid/questions/qa-7",
        None,
        {"model": "m1"},
    )
    resp = client.get(f"{base}/fragments", params={"model": "m1"})
    assert resp.json() == [{"file_name": "a.md", "is_source": True}]
    assert console.calls[-1][1] == (
        "/console/report/runs/job-mid/questions/qa-7/fragments"
    )


def test_deleting_a_run_reaches_the_benchmark_and_passes_a_refusal_on() -> None:
    handler, console = _handler()
    client = _app(handler)
    path = f"/benchmarks/endpoints/{SLUG}/report/runs/job-old"
    assert client.delete(path).status_code == 204
    assert console.calls[-1][:2] == ("DELETE", "/console/report/runs/job-old")

    console.raw = AsyncMock(  # type: ignore[method-assign]
        return_value=Reply(ok=False, status=409, detail="still running")
    )
    refused = client.delete(path)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "still running"


def test_summary_document_arrives_with_the_benchmarks_name_and_type() -> None:
    handler, console = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/summary.docx"
    )
    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04docx"
    assert resp.headers["content-type"] == DOCX
    assert resp.headers["content-disposition"] == (
        'attachment; filename="support-kb-2026-09-30-0300.docx"'
    )
    assert console.calls[-1][1] == "/console/report/runs/job-mid/summary.docx"


def test_the_excel_export_streams_through_with_its_name_and_type() -> None:
    handler, console = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/export.xlsx"
    )
    assert resp.status_code == 200
    assert resp.content == b"".join(XLSX_CHUNKS)
    assert resp.headers["content-type"] == XLSX
    assert resp.headers["content-disposition"] == (
        'attachment; filename="support-kb-run-2026-09-30-0300.xlsx"'
    )
    assert console.calls[-1][1] == "/console/report/runs/job-mid/export.xlsx"


def test_the_excel_export_passes_a_refusal_on() -> None:
    handler, _ = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/missing/export.xlsx"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "there is no job missing"


@pytest.mark.asyncio
async def test_the_client_streams_a_file_and_reads_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gone/export.xlsx"):
            return httpx.Response(404, json={"detail": "there is no job gone"})
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(
            200,
            content=b"".join(XLSX_CHUNKS),
            headers={
                "content-type": XLSX,
                "content-disposition": 'attachment; filename="a.xlsx"',
                "x-other": "dropped",
            },
        )

    real = httpx.AsyncClient
    monkeypatch.setattr(
        client_module.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(answer), **kw),
    )
    client = BenchmarkClient("http://benchmark:8200", "k")
    reply, body = await client.stream("/console/report/runs/j/export.xlsx")
    assert reply.ok and body is not None
    assert reply.headers == {
        "content-type": XLSX,
        "content-disposition": 'attachment; filename="a.xlsx"',
    }
    assert b"".join([chunk async for chunk in body]) == b"".join(XLSX_CHUNKS)

    reply, body = await client.stream("/console/report/runs/gone/export.xlsx")
    assert body is None
    assert (reply.ok, reply.status, reply.detail) == (
        False,
        404,
        "there is no job gone",
    )


# --- the console pairs filter ----------------------------------------------


def test_pairs_status_filter_is_forwarded_as_status() -> None:
    handler, console = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/console/pairs", params={"status": "rejected"}
    )
    assert resp.status_code == 200
    _, path, _, params = console.calls[-1]
    assert path == "/console/pairs"
    assert params["status"] == "rejected"
    assert "status_filter" not in params
