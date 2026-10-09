"""Benchmark results: the runs, their reports, and which run is published.

The benchmark knows the runs; the Space knows which one is published, because
the cards are stored here. Covered: the published/private filter paging on the
benchmark's side, the proxies passing their query and body through, the
summary document arriving with its own name and type, and publishing or
withdrawing a run by its job.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from syft_space.components.benchmarks import client as client_module
from syft_space.components.benchmarks.client import BenchmarkClient, Reply
from syft_space.components.benchmarks.entities import (
    BenchmarkConnection,
    BenchmarkTarget,
)
from syft_space.components.benchmarks.handlers import BenchmarkHandler, _RunCards
from syft_space.components.benchmarks.routes import build_benchmark_routes
from syft_space.components.endpoints.entities import Endpoint, EndpointQualityCard
from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    CARD_VERSION,
    KIND_ANSWERING,
    QualityMarketplaceResult,
    ReportQualityRequest,
)
from syft_space.components.tenants.dependency import get_tenant_dependency

TENANT = SimpleNamespace(id=uuid4(), name="default")
ENDPOINT_ID = uuid4()
SLUG = "support-kb"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_CHUNKS = (b"PK\x03\x04", b"xlsx-" * 1000, b"end")

STANDING = uuid4()
OLDER = uuid4()
WITHDRAWN = uuid4()


def _card_payload(job: str) -> dict:
    """A card as `/console/report` returns it — with the owner's extras."""
    return {
        "version": CARD_VERSION,
        "kind": KIND_ANSWERING,
        "arm": "model_with_context",
        "job": job,
        "checked_at": "2026-08-01T03:00:00+00:00",
        "score": 0.7,
        "fabrication_rate": 0.05,
        "reliable": True,
        "samples": 120,
        "score_label": "correct",
        "trust": {
            "judges": 3,
            "agreement": 0.9,
            "consistency": 0.9,
            "even_coverage": True,
            "failed": 0,
            "pending": 0,
            "flags": [],
            "doubts": ["owner-only prose"],
        },
    }


class _Console:
    """The benchmark's console: answers each route, remembers every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, dict]] = []
        self.runs = [
            {"job_id": "job-new", "created_at": "2026-09-30T03:00:00Z"},
            {"job_id": "job-mid", "created_at": "2026-09-20T03:00:00Z"},
            {"job_id": "job-old", "created_at": "2026-08-01T03:00:00Z"},
        ]
        self.card_job: str | None = None

    async def mint_session(self, key: str) -> Reply:
        return Reply(ok=True, data={"token": "t", "expires_at": "2026-10-03T18:00:00Z"})

    async def raw(
        self, method: str, path: str, *, body: object = None, params: dict | None = None
    ) -> Reply:
        params = params or {}
        self.calls.append((method, path, body, params))
        if path == "/console/report/runs":
            items = list(self.runs)
            if params.get("job_ids"):
                items = [
                    r for r in items if r["job_id"] in params["job_ids"].split(",")
                ]
            if params.get("exclude_job_ids"):
                gone = params["exclude_job_ids"].split(",")
                items = [r for r in items if r["job_id"] not in gone]
            return Reply(
                ok=True,
                data={
                    "in_progress": [{"job_id": "job-running", "state": "running"}],
                    "items": items,
                    "total": len(items),
                },
            )
        if path == "/console/report":
            job = self.card_job or params.get("job")
            return Reply(ok=True, data=_card_payload(job))
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


def _rows(standing: bool = True) -> list[tuple[UUID, str, datetime | None]]:
    """Cards newest first: job-mid stands, job-old has a card, a withdrawn one
    of job-new is newer than both."""
    now = datetime.now(timezone.utc)
    return [
        (WITHDRAWN, "job-new", now),
        (STANDING, "job-mid", None if standing else now),
        (OLDER, "job-old", now - timedelta(days=30)),
    ]


def _endpoint() -> SimpleNamespace:
    return SimpleNamespace(
        id=ENDPOINT_ID,
        slug=SLUG,
        name="Support KB",
        dataset_id=None,
        response_type="both",
        published_to=["m"],
    )


def _handler(
    rows: list[tuple[UUID, str, datetime | None]] | None = None,
    *,
    refusing: bool = False,
) -> tuple[BenchmarkHandler, _Console, PublishEndpointHandler]:
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

    stored = EndpointQualityCard(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        kind=KIND_ANSWERING,
        samples=120,
        reliable=True,
        checked_at=datetime(2026, 8, 1, 3, tzinfo=timezone.utc),
        report={},
    )
    endpoints = AsyncMock()
    endpoints.get_by_slug = AsyncMock(return_value=_endpoint())
    endpoints.quality_card_jobs = AsyncMock(
        return_value=_rows() if rows is None else rows
    )
    endpoints.record_quality = AsyncMock(return_value=stored)
    endpoints.restore_quality_card = AsyncMock(
        side_effect=lambda endpoint_id, tenant_id, card_id: SimpleNamespace(
            id=card_id, report={"job": "x"}
        )
    )
    endpoints.retract_quality = AsyncMock(return_value=1)

    marketplace = SimpleNamespace(id=uuid4(), name="Hub")
    publisher = PublishEndpointHandler(
        endpoint_repository=endpoints,
        marketplace_repository=SimpleNamespace(),  # type: ignore[arg-type]
        dataset_repository=SimpleNamespace(),  # type: ignore[arg-type]
        model_repository=SimpleNamespace(),  # type: ignore[arg-type]
        dataset_registry=SimpleNamespace(),  # type: ignore[arg-type]
        model_registry=SimpleNamespace(),  # type: ignore[arg-type]
    )
    outcome = QualityMarketplaceResult(
        marketplace_id=marketplace.id,
        marketplace_name="Hub",
        success=not refusing,
        error="hub said no" if refusing else None,
    )
    publisher._marketplaces_for = AsyncMock(return_value=[marketplace])  # type: ignore[method-assign]
    publisher._push_quality = AsyncMock(return_value=outcome)  # type: ignore[method-assign]
    publisher._retract_quality = AsyncMock(return_value=outcome)  # type: ignore[method-assign]

    handler = BenchmarkHandler(
        connection_repository=connections,
        target_repository=targets,
        endpoint_repository=endpoints,
        dataset_repository=AsyncMock(),
        dataset_registry=SimpleNamespace(),
        publish_handler=publisher,
    )
    handler._client = lambda connection: console  # type: ignore[method-assign,assignment]
    handler._console_client = lambda connection, token: console  # type: ignore[method-assign,assignment]
    return handler, console, publisher


def _app(handler: BenchmarkHandler) -> TestClient:
    app = FastAPI()
    app.include_router(build_benchmark_routes(handler))
    app.dependency_overrides[get_tenant_dependency] = lambda: TENANT
    return TestClient(app)


def _runs_call(console: _Console) -> dict:
    return next(c for c in console.calls if c[1] == "/console/report/runs")[3]


# --- the runs list ----------------------------------------------------------


@pytest.mark.asyncio
async def test_every_run_says_whether_it_is_published_and_which_card_is_its() -> None:
    handler, console, _ = _handler()
    data = await handler.list_report_runs(TENANT, SLUG, "all", {"limit": 25})
    marks = {r["job_id"]: (r["published"], r["card_id"]) for r in data["items"]}
    assert marks == {
        "job-new": (False, str(WITHDRAWN)),
        "job-mid": (True, str(STANDING)),
        "job-old": (False, str(OLDER)),
    }
    params = _runs_call(console)
    assert "job_ids" not in params and "exclude_job_ids" not in params


@pytest.mark.asyncio
async def test_published_filter_is_applied_by_the_benchmark_so_paging_holds() -> None:
    handler, console, _ = _handler()
    data = await handler.list_report_runs(
        TENANT, SLUG, "published", {"limit": 10, "offset": 0}
    )
    assert _runs_call(console)["job_ids"] == "job-mid"
    assert [r["job_id"] for r in data["items"]] == ["job-mid"]
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_private_filter_excludes_the_published_run_on_the_benchmark() -> None:
    handler, console, _ = _handler()
    data = await handler.list_report_runs(TENANT, SLUG, "private", {})
    assert _runs_call(console)["exclude_job_ids"] == "job-mid"
    assert [r["job_id"] for r in data["items"]] == ["job-new", "job-old"]
    assert not any(r["published"] for r in data["items"])


@pytest.mark.asyncio
async def test_published_filter_with_nothing_published_is_empty_but_shows_progress() -> (
    None
):
    handler, _, _ = _handler(rows=_rows(standing=False))
    data = await handler.list_report_runs(TENANT, SLUG, "published", {})
    assert data["items"] == [] and data["total"] == 0
    assert data["in_progress"] == [{"job_id": "job-running", "state": "running"}]


@pytest.mark.asyncio
async def test_private_with_nothing_published_lists_every_run() -> None:
    handler, console, _ = _handler(rows=[])
    data = await handler.list_report_runs(TENANT, SLUG, "private", {})
    assert "exclude_job_ids" not in _runs_call(console)
    assert len(data["items"]) == 3
    assert all(r["card_id"] is None for r in data["items"])


@pytest.mark.asyncio
async def test_an_unknown_status_is_refused() -> None:
    handler, _, _ = _handler()
    with pytest.raises(HTTPException) as caught:
        await handler.list_report_runs(TENANT, SLUG, "draft", {})
    assert caught.value.status_code == 422


def test_runs_route_passes_dates_and_paging_through() -> None:
    handler, console, _ = _handler()
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
async def test_a_runs_report_carries_its_published_state_too() -> None:
    handler, console, _ = _handler()
    data = await handler.get_report_run(TENANT, SLUG, "job-mid")
    assert console.calls[-1][1] == "/console/report/runs/job-mid"
    assert data["run"]["published"] is True
    assert data["run"]["card_id"] == str(STANDING)
    assert data["timing"] == TIMING


def test_questions_route_passes_every_query_parameter_through() -> None:
    handler, console, _ = _handler()
    query = {
        "model": "m1",
        "group": "fixed",
        "generator": "mcq",
        "q": "tax",
        "excluded": "only",
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
    handler, console, _ = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/{part}", params=query
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}
    method, path, _, params = console.calls[-1]
    assert (method, path) == ("GET", f"/console/report/runs/job-mid/{part}")
    assert params == query


def test_a_benchmark_refusal_keeps_its_status() -> None:
    handler, _, _ = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/report/runs/missing/questions",
        params={"model": "m1"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "there is no job missing"


def test_question_detail_and_fragments_are_proxied_with_the_model() -> None:
    handler, console, _ = _handler()
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


def test_excluding_and_restoring_a_question_reach_the_benchmark() -> None:
    handler, console, _ = _handler()
    client = _app(handler)
    path = f"/benchmarks/endpoints/{SLUG}/report/runs/job-mid/questions/qa-7/exclusion"
    body = {"reason": "wrong gold answer", "retire": True}
    assert client.put(path, json=body).status_code == 200
    assert console.calls[-1][:3] == (
        "PUT",
        "/console/report/runs/job-mid/questions/qa-7/exclusion",
        body,
    )
    assert client.delete(path).status_code == 204
    assert console.calls[-1][:2] == (
        "DELETE",
        "/console/report/runs/job-mid/questions/qa-7/exclusion",
    )


def test_summary_document_arrives_with_the_benchmarks_name_and_type() -> None:
    handler, console, _ = _handler()
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
    handler, console, _ = _handler()
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
    handler, _, _ = _handler()
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


# --- publishing a run -------------------------------------------------------


@pytest.mark.asyncio
async def test_publishing_a_run_with_a_card_rebuilds_it_from_live_figures() -> None:
    """Republishing after overrides or exclusions must carry the new numbers."""
    handler, console, publisher = _handler()
    out = await handler.publish_run(TENANT, SLUG, "job-old")
    assert any(c[1] == "/console/report" for c in console.calls)
    publisher.endpoint_repository.record_quality.assert_awaited_once()
    stored_id = publisher.endpoint_repository.record_quality.return_value.id
    assert stored_id != OLDER
    publisher.endpoint_repository.restore_quality_card.assert_awaited_once_with(
        ENDPOINT_ID, TENANT.id, stored_id
    )
    assert out == {"published": True, "card_id": str(stored_id), "refused": []}


@pytest.mark.asyncio
async def test_publishing_an_old_run_without_a_card_builds_stores_and_publishes() -> (
    None
):
    handler, console, publisher = _handler(rows=_rows()[:2], refusing=True)
    out = await handler.publish_run(TENANT, SLUG, "job-old")

    method, path, body, params = next(
        c for c in console.calls if c[1] == "/console/report"
    )
    assert method == "POST"
    assert params == {"job": "job-old", "record": "true"}
    assert body == {"job": "job-old", "record": True}

    recorded = publisher.endpoint_repository.record_quality.await_args.kwargs["report"]
    assert recorded["job"] == "job-old"
    # The owner's extras never reach a stored or published card.
    assert "score_label" not in recorded
    assert "doubts" not in recorded["trust"]

    stored_id = publisher.endpoint_repository.record_quality.return_value.id
    publisher.endpoint_repository.restore_quality_card.assert_awaited_once_with(
        ENDPOINT_ID, TENANT.id, stored_id
    )
    assert publisher._push_quality.await_count == 1  # type: ignore[attr-defined]
    assert out["published"] is True
    assert out["card_id"] == str(stored_id)
    assert [r["marketplace_name"] for r in out["refused"]] == ["Hub"]
    assert out["refused"][0]["error"] == "hub said no"


@pytest.mark.asyncio
async def test_a_card_built_for_another_run_is_not_stored() -> None:
    handler, console, publisher = _handler(rows=[])
    console.card_job = "job-new"
    with pytest.raises(HTTPException) as caught:
        await handler.publish_run(TENANT, SLUG, "job-old")
    assert caught.value.status_code == 502
    publisher.endpoint_repository.record_quality.assert_not_awaited()


def test_publish_and_unpublish_routes() -> None:
    handler, _, publisher = _handler()
    client = _app(handler)
    base = f"/benchmarks/endpoints/{SLUG}/report/runs"
    resp = client.post(f"{base}/job-mid/publish")
    assert resp.status_code == 200 and resp.json()["published"] is True
    resp = client.post(f"{base}/job-mid/unpublish")
    assert resp.status_code == 200
    assert resp.json() == {"published": False, "refused": []}
    publisher.endpoint_repository.retract_quality.assert_awaited_once()


@pytest.mark.asyncio
async def test_unpublishing_a_run_that_is_not_the_published_one_is_refused() -> None:
    handler, _, publisher = _handler()
    with pytest.raises(HTTPException) as caught:
        await handler.unpublish_run(TENANT, SLUG, "job-old")
    assert caught.value.status_code == 409
    assert caught.value.detail == "This run is not the published one"
    publisher.endpoint_repository.retract_quality.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpublishing_when_nothing_is_published_is_refused() -> None:
    handler, _, _ = _handler(rows=_rows(standing=False))
    with pytest.raises(HTTPException) as caught:
        await handler.unpublish_run(TENANT, SLUG, "job-mid")
    assert caught.value.status_code == 409
    assert caught.value.detail == "No run of this endpoint is published"


# --- the console pairs filter ----------------------------------------------


def test_pairs_status_filter_is_forwarded_as_status() -> None:
    handler, console, _ = _handler()
    resp = _app(handler).get(
        f"/benchmarks/endpoints/{SLUG}/console/pairs", params={"status": "rejected"}
    )
    assert resp.status_code == 200
    _, path, _, params = console.calls[-1]
    assert path == "/console/pairs"
    assert params["status"] == "rejected"
    assert "status_filter" not in params


# --- which card stands -----------------------------------------------------


def test_the_standing_card_is_the_newest_not_withdrawn_and_wins_its_job() -> None:
    now = datetime.now(timezone.utc)
    older_of_same_job = uuid4()
    cards = _RunCards.from_rows(
        [
            (uuid4(), "job-b", now),  # newer card of job-b, withdrawn
            (STANDING, "job-b", None),
            (older_of_same_job, "job-a", None),  # not withdrawn, but not newest
            (uuid4(), "", None),
        ]
    )
    assert cards.standing_job == "job-b"
    assert cards.by_job["job-b"] == STANDING
    run = {"job_id": "job-a"}
    cards.mark(run)
    assert run == {
        "job_id": "job-a",
        "published": False,
        "card_id": str(older_of_same_job),
    }


@pytest.mark.asyncio
async def test_card_jobs_are_read_newest_first_in_one_query(main_db) -> None:
    repo = EndpointRepository(main_db)
    tenant_id = uuid4()
    async with main_db.get_session() as session:
        session.add(
            Endpoint(
                id=ENDPOINT_ID,
                tenant_id=tenant_id,
                name="KB",
                slug=SLUG,
                response_type="both",
                model_id=uuid4(),
            )
        )
        await session.commit()

    async def card(job: str, day: int) -> EndpointQualityCard:
        report = ReportQualityRequest.model_validate(
            {**_card_payload(job), "checked_at": f"2026-09-{day:02d}T03:00:00Z"}
        )
        stored = await repo.record_quality(
            ENDPOINT_ID,
            tenant_id,
            kind=report.kind,
            score=report.score,
            fabrication_rate=report.fabrication_rate,
            samples=report.samples,
            reliable=report.reliable,
            checked_at=report.checked_at,
            report=report.model_dump(mode="json"),
        )
        assert stored is not None
        return stored

    first = await card("job-1", 1)
    second = await card("job-2", 2)
    await repo.restore_quality_card(ENDPOINT_ID, tenant_id, first.id)

    rows = await repo.quality_card_jobs(ENDPOINT_ID, tenant_id)
    assert [(r[0], r[1]) for r in rows] == [(second.id, "job-2"), (first.id, "job-1")]
    assert rows[0][2] is not None and rows[1][2] is None
    assert _RunCards.from_rows(rows).standing_job == "job-1"
