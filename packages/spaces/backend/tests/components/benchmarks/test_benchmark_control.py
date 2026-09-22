"""Wiring a benchmark up and setting it going.

A Space ships without a benchmark. What is covered here is what would be
expensive to get wrong: a key silently revoked by renaming a connection, a
setting stored here and never reaching the service that measures, a benchmark
being down taking the settings page with it, and an endpoint nobody opted in
reading as one that scored zero.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_space.components.benchmarks.client import Reply
from syft_space.components.benchmarks.entities import (
    BenchmarkConnection,
    BenchmarkTarget,
)
from syft_space.components.benchmarks.handlers import BenchmarkHandler
from syft_space.components.benchmarks.schemas import (
    ConnectionRequest,
    ConnectionSettings,
    RunRequest,
    TargetRequest,
)

TENANT = SimpleNamespace(id=uuid4(), name="default")
ENDPOINT_ID = uuid4()
DATASET_ID = uuid4()


def _endpoint(**overrides: object) -> SimpleNamespace:
    body = {
        "id": ENDPOINT_ID,
        "slug": "support-kb",
        "name": "Support KB",
        "dataset_id": DATASET_ID,
    }
    body.update(overrides)
    return SimpleNamespace(**body)


def _connection(**overrides: object) -> BenchmarkConnection:
    body = {
        "tenant_id": TENANT.id,
        "name": "Local benchmark",
        "url": "http://benchmark:8200",
        "token": "secret",
        "space_url": "http://space:8081",
        "chroma_host": "space",
        "chroma_port": 8100,
        "is_default": True,
        "is_active": True,
    }
    body.update(overrides)
    return BenchmarkConnection(**body)


class _Client:
    """A benchmark that answers, and remembers what it was told."""

    def __init__(self, reachable: bool = True) -> None:
        self.reachable = reachable
        self.targets: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.runs: list[tuple[str, dict]] = []
        self.known_jobs: list[dict] = []
        self.known_next_run: str | None = None
        self.snapshots = 0

    async def snapshot(self) -> SimpleNamespace:
        self.snapshots += 1
        return SimpleNamespace(
            reachable=self.reachable,
            detail="" if self.reachable else "benchmark is not answering",
            capabilities={"arms": ["closed_book"]} if self.reachable else {},
            # What the benchmark says about its fields today. A field that grew
            # a catalogue is the case this whole refresh exists for.
            fields=(
                {
                    "probe": [],
                    "instrument": [{"name": "judge_models", "catalog": "models"}],
                }
                if self.reachable
                else {}
            ),
            defaults={"probe": {"retrieval_top_k": 5}} if self.reachable else {},
        )

    async def put_target(self, key: str, spec: dict) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        self.targets[key] = spec
        return Reply(ok=True, data=spec)

    async def delete_target(self, key: str) -> Reply:
        self.deleted.append(key)
        return Reply(ok=True)

    async def check_target(self, key: str) -> Reply:
        return Reply(ok=True, data={"ok": True, "corpus": True, "endpoint": True})

    async def start_run(self, key: str, request: dict) -> Reply:
        self.runs.append((key, request))
        return Reply(
            ok=True, data={"id": "job-1", "state": "queued", "phase": "pending"}
        )

    async def target(self, key: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(
            ok=True,
            data={**self.targets.get(key, {}), "next_run_at": self.known_next_run},
        )

    async def jobs(self, key: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(ok=True, data=list(self.known_jobs))

    async def cancel(self, job_id: str) -> Reply:
        return Reply(
            ok=True, data={"id": job_id, "state": "cancelled", "phase": "done"}
        )

    async def delete_job(self, job_id: str) -> Reply:
        if job_id == "still-running":
            return Reply(ok=False, status=409, detail="job is still queued or running")
        if job_id not in {row["id"] for row in self.known_jobs}:
            return Reply(ok=False, status=404, detail=f"there is no job {job_id}")
        self.known_jobs = [row for row in self.known_jobs if row["id"] != job_id]
        return Reply(ok=True)

    async def models(self, query: dict) -> Reply:
        self.asked_for_models = query
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(
            ok=True,
            data={
                "models": [{"id": "anthropic/claude-sonnet-5", "name": "Sonnet"}],
                "vendors": ["anthropic"],
                "pins": {
                    "~anthropic/claude-sonnet-latest": "anthropic/claude-sonnet-5"
                },
                "fetched": {"openrouter": "2026-09-20T11:02:57+00:00"},
                "total": 1,
            },
        )

    async def refresh_models(self) -> Reply:
        if not self.reachable:
            return Reply(
                ok=False,
                status=403,
                detail="calls outside are not allowed: add openrouter.ai to "
                "external_hosts",
            )
        return Reply(ok=True, data={"models": [], "total": 0})


def _handler(
    client: _Client | None = None,
    connections: list[BenchmarkConnection] | None = None,
    target: BenchmarkTarget | None = None,
    endpoint: SimpleNamespace | None = None,
    settings_repo: AsyncMock | None = None,
) -> tuple[BenchmarkHandler, _Client]:
    rows = connections if connections is not None else []
    talker = client or _Client()

    connection_repo = AsyncMock()
    connection_repo.list_for_tenant = AsyncMock(return_value=rows)
    connection_repo.get = AsyncMock(return_value=rows[0] if rows else None)
    connection_repo.default_for = AsyncMock(return_value=rows[0] if rows else None)
    connection_repo.create = AsyncMock(side_effect=lambda row: row)
    connection_repo.update = AsyncMock(side_effect=lambda row: row)
    connection_repo.delete = AsyncMock(return_value=True)
    connection_repo.clear_default = AsyncMock()

    target_repo = AsyncMock()
    target_repo.for_endpoint = AsyncMock(return_value=target)
    target_repo.list_for_tenant = AsyncMock(return_value=[target] if target else [])
    target_repo.count_for_connection = AsyncMock(return_value=0)
    target_repo.create = AsyncMock(side_effect=lambda row: row)
    target_repo.update = AsyncMock(side_effect=lambda row: row)
    target_repo.delete = AsyncMock(return_value=True)
    target_repo.remember_job = AsyncMock()
    target_repo.mark_synced = AsyncMock()

    endpoint_repo = AsyncMock()
    endpoint_repo.get_by_slug = AsyncMock(return_value=endpoint or _endpoint())
    endpoint_repo.get_by_id = AsyncMock(return_value=endpoint or _endpoint())

    dataset_repo = AsyncMock()
    dataset_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(dtype="blogspot_chromadb", configuration={})
    )
    registry = SimpleNamespace(
        get_dataset_type=lambda dtype: (
            lambda config: SimpleNamespace(collection_name="Collection_support_kb")
        )
    )

    handler = BenchmarkHandler(
        connection_repository=connection_repo,
        target_repository=target_repo,
        endpoint_repository=endpoint_repo,
        dataset_repository=dataset_repo,
        dataset_registry=registry,
        settings_repository=settings_repo,
    )
    handler._client = lambda connection: talker  # type: ignore[method-assign]
    return handler, talker


# --- connections ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_first_benchmark_becomes_the_default_without_being_asked() -> None:
    """A Space with one benchmark should never be told which one to use.

    A default nobody set is the commonest way to end up with endpoints that
    quietly measure nothing.
    """
    handler, _ = _handler()
    made = await handler.connect(
        TENANT, ConnectionRequest(name="Local", url="http://benchmark:8200")
    )
    assert made.is_default is True


@pytest.mark.asyncio
async def test_connecting_a_benchmark_is_read_as_consent_to_report() -> None:
    """Only the owner can reach this route, and using it already says yes.

    Asking him to also find `benchmarks_mode` on a settings page and flip it
    by hand would be the same consent asked for twice — once loudly, by
    wiring a benchmark up, and once again in fine print he may never read.
    """
    settings_repo = AsyncMock()
    settings_repo.get_public_url = AsyncMock(return_value="")
    handler, _ = _handler(settings_repo=settings_repo)
    await handler.connect(
        TENANT, ConnectionRequest(name="Local", url="http://benchmark:8200")
    )
    settings_repo.enable_benchmarks_if_untouched.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_control_key_never_comes_back_out() -> None:
    """Only whether there is one. The form has no business knowing it."""
    handler, _ = _handler(connections=[_connection()])
    view = (await handler.list_connections(TENANT))[0]
    assert view.has_token is True
    assert "secret" not in view.model_dump_json()


@pytest.mark.asyncio
async def test_renaming_a_connection_does_not_revoke_its_key() -> None:
    """The form was never told the key and cannot send it back.

    Without this rule, renaming would silently take the benchmark's access
    away, and it would be found out at the next nightly run.
    """
    row = _connection()
    handler, _ = _handler(connections=[row])
    await handler.update_connection(
        TENANT,
        row.id,
        ConnectionRequest(name="Renamed", url=row.url, space_url=row.space_url),
    )
    assert row.token == "secret"


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_still_connects_and_says_why() -> None:
    """The page must open and say what is wrong, not refuse to exist."""
    handler, _ = _handler(client=_Client(reachable=False))
    made = await handler.connect(
        TENANT, ConnectionRequest(name="Local", url="http://benchmark:8200")
    )
    assert made.reachable is False
    assert made.detail


@pytest.mark.asyncio
async def test_saving_settings_pushes_them_to_every_endpoint_it_measures() -> None:
    """Settings reach the benchmark only through targets, and every one carries them.

    Stored here and not there, a setting would take effect on the next manual
    run and never on the nightly one.
    """
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)
    await handler.save_settings(
        TENANT,
        row.id,
        ConnectionSettings(
            instrument={"judge_model": "panel"}, probe={"retrieval_top_k": 9}
        ),
    )
    assert client.targets["support-kb"]["instrument"] == {"judge_model": "panel"}
    assert client.targets["support-kb"]["probe"]["retrieval_top_k"] == 9


# --- targets ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_endpoint_nobody_opted_in_is_not_measured_rather_than_zero() -> None:
    """``measured: false`` is not a score and must never be rendered as one."""
    handler, _ = _handler(connections=[_connection()])
    view = await handler.get_target(TENANT, "support-kb")
    assert view.measured is False
    assert view.last_job is None


@pytest.mark.asyncio
async def test_the_endpoint_layer_lies_on_top_of_the_space_wide_one() -> None:
    """Three layers, and the nearest to the node wins.

    Whoever set the endpoint's value knew more about that endpoint than
    whoever set the Space-wide one.
    """
    row = _connection(probe={"retrieval_top_k": 5, "similarity_threshold": 0.3})
    handler, client = _handler(connections=[row])
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(probe={"retrieval_top_k": 11})
    )
    sent = client.targets["support-kb"]["probe"]
    assert sent == {"retrieval_top_k": 11, "similarity_threshold": 0.3}


@pytest.mark.asyncio
async def test_the_collection_is_resolved_rather_than_typed() -> None:
    """The owner picked a dataset, not a collection.

    Making him find the name in ChromaDB would be asking him to know an
    implementation detail of his own Space.
    """
    handler, client = _handler(connections=[_connection()])
    await handler.save_target(TENANT, "support-kb", TargetRequest())
    assert client.targets["support-kb"]["collection"] == "Collection_support_kb"


@pytest.mark.asyncio
async def test_a_collection_named_by_hand_wins_over_the_resolved_one() -> None:
    """Resolution can be wrong, and then the owner must be able to say so."""
    handler, client = _handler(connections=[_connection()])
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(collection="Collection_legacy")
    )
    assert client.targets["support-kb"]["collection"] == "Collection_legacy"


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_block_saving() -> None:
    """The owner has already made the decision; he needs somewhere to record it.

    ``synced_at`` is what says whether it got through, and the page says so.
    """
    handler, _ = _handler(client=_Client(reachable=False), connections=[_connection()])
    await handler.save_target(TENANT, "support-kb", TargetRequest())
    handler.targets.mark_synced.assert_not_called()  # type: ignore[attr-defined]
    handler.targets.create.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_measuring_needs_a_benchmark_to_be_connected_first() -> None:
    """Refusing with a reason, rather than storing a target nothing will measure."""
    handler, _ = _handler(connections=[])
    with pytest.raises(HTTPException) as refused:
        await handler.save_target(TENANT, "support-kb", TargetRequest())
    assert refused.value.status_code == 409
    assert "Connect one" in refused.value.detail


@pytest.mark.asyncio
async def test_dropping_an_endpoint_drops_it_at_the_benchmark_too() -> None:
    """Otherwise it keeps measuring on schedule, and nothing here would show it."""
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)
    await handler.stop_measuring(TENANT, "support-kb")
    assert client.deleted == ["support-kb"]


# --- runs -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_paused_endpoint_is_not_measured_on_request_either() -> None:
    """Paused means paused — otherwise the button quietly overrides the switch."""
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        connection_id=row.id,
        enabled=False,
    )
    handler, _ = _handler(connections=[row], target=target)
    with pytest.raises(HTTPException) as refused:
        await handler.start_run(TENANT, "support-kb", RunRequest())
    assert refused.value.status_code == 409


@pytest.mark.asyncio
async def test_a_run_is_started_against_settings_the_benchmark_has_been_told() -> None:
    """Otherwise the run measures with the previous settings and reports as new."""
    row = _connection(probe={"retrieval_top_k": 5})
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)
    await handler.start_run(TENANT, "support-kb", RunRequest(limit=2))
    assert client.targets["support-kb"]["probe"] == {"retrieval_top_k": 5}
    assert client.runs == [("support-kb", {"publish": True, "limit": 2})]


@pytest.mark.asyncio
async def test_an_endpoint_layer_cannot_carry_the_instrument() -> None:
    """Judges and thresholds are what the card declares in ``instrument``.

    Letting one endpoint use different ones would make two endpoints of the
    same Space quietly incomparable while the card still promised otherwise.
    """
    assert "instrument" not in TargetRequest.model_fields


# --- job history -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_finished_job_can_be_discarded() -> None:
    """Deleting it removes it from the history the benchmark hands back."""
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)
    client.known_jobs = [{"id": "job-1", "state": "succeeded", "phase": "done"}]

    await handler.delete_job(TENANT, "support-kb", "job-1")

    assert await handler.list_jobs(TENANT, "support-kb") == []


@pytest.mark.asyncio
async def test_a_job_still_running_is_not_discarded() -> None:
    """The benchmark itself refuses it (409); this must not swallow that."""
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(connections=[row], target=target)

    with pytest.raises(HTTPException) as refused:
        await handler.delete_job(TENANT, "support-kb", "still-running")
    assert refused.value.status_code == 409


@pytest.mark.asyncio
async def test_deleting_a_job_that_does_not_exist_answers_404() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(connections=[row], target=target)

    with pytest.raises(HTTPException) as refused:
        await handler.delete_job(TENANT, "support-kb", "no-such-job")
    assert refused.value.status_code == 404


# --- memory of the last run --------------------------------------------------


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_erase_the_last_run() -> None:
    """A page that empties out while the service is down reads as "never measured".

    That is a different claim, and a false one.
    """
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        connection_id=row.id,
        last_job={"id": "old", "state": "succeeded", "phase": "done"},
    )
    handler, _ = _handler(
        client=_Client(reachable=False), connections=[row], target=target
    )
    jobs = await handler.list_jobs(TENANT, "support-kb")
    assert [job.id for job in jobs] == ["old"]


@pytest.mark.asyncio
async def test_a_run_the_benchmark_has_forgotten_leaves_the_page_too() -> None:
    """An explicit "no jobs" is an answer, not silence.

    The cache exists for when the service does not reply. Outliving the
    service's own "there are none" would leave a measurement on the page with
    nothing behind it — and leave it there forever.
    """
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        connection_id=row.id,
        last_job={"id": "old", "state": "succeeded", "phase": "done"},
    )
    handler, _ = _handler(connections=[row], target=target)
    assert await handler.list_jobs(TENANT, "support-kb") == []
    handler.targets.remember_job.assert_awaited_with(target.id, None)  # type: ignore[attr-defined]


# --- the schedule ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_schedule_set_here_reaches_the_benchmark() -> None:
    """The Space stores it, but it is the benchmark that fires it.

    A schedule that stayed in this database would be a form the owner fills in
    and a measurement that never happens — which is what it was until the
    benchmark grew a scheduler.
    """
    handler, client = _handler(connections=[_connection()], endpoint=_endpoint())
    await handler.save_target(
        TENANT,
        "support-kb",
        TargetRequest(enabled=True, schedule="24h", schedule_at="03:00"),
    )
    spec = client.targets["support-kb"]
    assert spec["schedule"] == "24h"
    assert spec["schedule_at"] == "03:00"


@pytest.mark.asyncio
async def test_when_it_next_runs_is_asked_of_the_benchmark_not_invented_here() -> None:
    """Two computations of one moment part company on exactly the question this
    is shown to answer — "why has it not run yet"."""
    client = _Client()
    client.known_next_run = "2026-09-18T03:00:00Z"
    handler, _ = _handler(
        client=client,
        connections=[_connection()],
        endpoint=_endpoint(),
        target=BenchmarkTarget(
            tenant_id=TENANT.id,
            endpoint_id=ENDPOINT_ID,
            enabled=True,
            schedule="24h",
            schedule_at="03:00",
        ),
    )
    out = await handler.get_target(TENANT, "support-kb")
    assert out.next_run_at is not None
    assert out.next_run_at.hour == 3
    assert out.next_run_at.tzinfo is not None


@pytest.mark.asyncio
async def test_a_benchmark_that_cannot_answer_leaves_the_moment_empty() -> None:
    """Rather than guessing it from the interval. An invented moment would be
    indistinguishable from a real one and wrong whenever it mattered."""
    handler, _ = _handler(
        client=_Client(reachable=False),
        connections=[_connection()],
        endpoint=_endpoint(),
        target=BenchmarkTarget(
            tenant_id=TENANT.id,
            endpoint_id=ENDPOINT_ID,
            enabled=True,
            schedule="24h",
            schedule_at="03:00",
        ),
    )
    out = await handler.get_target(TENANT, "support-kb")
    assert out.schedule == "24h"
    assert out.next_run_at is None


# --- the model catalogue ----------------------------------------------------


@pytest.mark.asyncio
async def test_the_catalogue_is_passed_through_unshaped() -> None:
    """The Space does not model what a benchmark knows about a model.

    Every field named on this side is a field that would need a release here
    before the benchmark may grow one — the same rule that keeps /schema from
    being repeated in this codebase.
    """
    connection = _connection()
    handler, client = _handler(connections=[connection])

    out = await handler.models(TENANT, connection.id, {"q": "claude", "limit": 0})

    assert out["models"][0]["id"] == "anthropic/claude-sonnet-5"
    assert out["pins"]
    assert out["fetched"]["openrouter"]
    assert client.asked_for_models["q"] == "claude"


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_look_like_an_empty_catalogue() -> None:
    """An empty list reads as "there are no models", and the owner would go
    looking for the mistake in their own configuration."""
    connection = _connection()
    handler, _ = _handler(client=_Client(reachable=False), connections=[connection])

    with pytest.raises(HTTPException) as refusal:
        await handler.models(TENANT, connection.id, {})

    assert refusal.value.status_code == 502


@pytest.mark.asyncio
async def test_a_refused_refresh_keeps_the_benchmarks_own_words() -> None:
    """A refresh is a call outside the benchmark's perimeter, and a benchmark
    that forbids it answers with the host to open. Flattening that into 502
    would replace an instruction with "something went wrong"."""
    connection = _connection()
    handler, _ = _handler(client=_Client(reachable=False), connections=[connection])

    with pytest.raises(HTTPException) as refusal:
        await handler.refresh_models(TENANT, connection.id)

    assert refusal.value.status_code == 403
    assert "external_hosts" in refusal.value.detail


# --- keeping the benchmark's description current ----------------------------


@pytest.mark.asyncio
async def test_a_stale_description_is_refreshed_when_the_page_opens() -> None:
    """The reason /schema exists is that a benchmark can grow a field.

    Cached for ever, that promise quietly fails: the benchmark is upgraded, the
    form keeps drawing yesterday's fields, and nobody knows to press Check. It
    cost exactly that once — a settings field that had grown a model catalogue
    on the benchmark side went on being drawn as a text box here.
    """
    from datetime import datetime, timedelta, timezone

    stale = _connection(
        fields={"instrument": [{"name": "judge_models"}]},
        checked_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    handler, client = _handler(connections=[stale])

    listed = await handler.list_connections(TENANT)

    assert client.snapshots == 1
    assert listed[0].fields["instrument"][0]["catalog"] == "models"


@pytest.mark.asyncio
async def test_a_fresh_description_is_not_asked_for_again() -> None:
    """A page that opens fine without a round trip should not pay for one."""
    from datetime import datetime, timezone

    fresh = _connection(
        fields={"instrument": [{"name": "judge_models"}]},
        checked_at=datetime.now(timezone.utc),
    )
    handler, client = _handler(connections=[fresh])

    await handler.list_connections(TENANT)

    assert client.snapshots == 0


@pytest.mark.asyncio
async def test_a_naive_timestamp_does_not_take_the_page_down() -> None:
    """SQLite hands the moment back without a zone, and it was written in UTC.

    Compared against an aware "now" that raises — and it would raise inside the
    call that draws the settings page, which is the one place this cache exists
    to keep openable.
    """
    from datetime import datetime, timezone

    naive = _connection(
        fields={"instrument": [{"name": "judge_models"}]},
        checked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    handler, client = _handler(connections=[naive])

    listed = await handler.list_connections(TENANT)

    assert client.snapshots == 0, "a moment written minutes ago is not stale"
    assert listed[0].fields


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_leaves_the_page_standing() -> None:
    """Keeping the cache current must not cost what the cache is for."""
    stale = _connection(fields={"instrument": [{"name": "judge_models"}]})
    handler, _ = _handler(client=_Client(reachable=False), connections=[stale])

    listed = await handler.list_connections(TENANT)

    # The description it had, not an empty form: a benchmark being down is a
    # reason to say so on the page, not to forget how it is configured.
    assert listed[0].fields["instrument"][0]["name"] == "judge_models"
    assert listed[0].reachable is False
