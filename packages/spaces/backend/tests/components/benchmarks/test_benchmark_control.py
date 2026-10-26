"""Benchmark connections, targets, runs and the console proxy."""

from __future__ import annotations

from datetime import datetime, timezone
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
    ProviderUrls,
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
        self.runs: list[tuple[str, dict]] = []
        self.known_jobs: list[dict] = []
        self.known_next_run: str | None = None
        self.snapshots = 0
        self.settings_values: dict[str, object] = {}
        self.credentials: dict[str, str] = {}
        self.console_calls: list[tuple[str, str, object, dict]] = []

    async def snapshot(self) -> SimpleNamespace:
        self.snapshots += 1
        return SimpleNamespace(
            reachable=self.reachable,
            detail="" if self.reachable else "benchmark is not answering",
            capabilities={"arms": ["closed_book"]} if self.reachable else {},
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

    async def window(self, key: str, days: int | None = None) -> Reply:
        self.window_asks = (key, days)
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(
            ok=True,
            data={"count": 4, "undated": 1, "total": 9, "window_days": days or 1},
        )

    async def jobs(self, key: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(ok=True, data=list(self.known_jobs))

    async def cancel(self, job_id: str) -> Reply:
        return Reply(
            ok=True, data={"id": job_id, "state": "cancelled", "phase": "done"}
        )

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

    async def mint_session(self, key: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(
            ok=True,
            data={"token": f"token-for-{key}", "expires_at": "2026-09-24T18:00:00Z"},
        )

    async def get_settings(self) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(ok=True, data={"values": dict(self.settings_values)})

    async def put_settings(self, values: dict) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        self.settings_values.update(values)
        return Reply(ok=True, data={"values": dict(self.settings_values)})

    async def list_credentials(self) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        return Reply(
            ok=True,
            data=[
                {"name": name, "updated_at": "2026-09-24T18:00:00Z"}
                for name in self.credentials
            ],
        )

    async def put_credential(self, name: str, value: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        self.credentials[name] = value
        return Reply(ok=True)

    async def delete_credential(self, name: str) -> Reply:
        if not self.reachable:
            return Reply(ok=False, detail="down")
        self.credentials.pop(name, None)
        return Reply(ok=True)

    async def raw(
        self, method: str, path: str, *, body: object = None, params: dict | None = None
    ) -> Reply:
        self.console_calls.append((method, path, body, params or {}))
        if not self.reachable:
            return Reply(ok=False, detail="down")
        if method == "GET" and path in ("/console/pairs", "/console/results"):
            return Reply(ok=True, data={"items": [], "total": 0})
        if method == "DELETE":
            return Reply(ok=True, data=None)
        return Reply(ok=True, data={"ok": True})


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
    handler._console_client = lambda connection, token: talker  # type: ignore[method-assign]
    return handler, talker


# --- connections ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_first_benchmark_becomes_the_default_without_being_asked() -> None:
    """The first connection becomes the default."""
    handler, _ = _handler()
    made = await handler.connect(
        TENANT, ConnectionRequest(name="Local", url="http://benchmark:8200")
    )
    assert made.is_default is True


@pytest.mark.asyncio
async def test_the_control_key_never_comes_back_out() -> None:
    """The response says whether a key is set, never the key."""
    handler, _ = _handler(connections=[_connection()])
    view = (await handler.list_connections(TENANT))[0]
    assert view.has_token is True
    assert "secret" not in view.model_dump_json()


@pytest.mark.asyncio
async def test_renaming_a_connection_does_not_revoke_its_key() -> None:
    """An update without a token keeps the stored one."""
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
    """An unreachable benchmark is reported, not raised."""
    handler, _ = _handler(client=_Client(reachable=False))
    made = await handler.connect(
        TENANT, ConnectionRequest(name="Local", url="http://benchmark:8200")
    )
    assert made.reachable is False
    assert made.detail


@pytest.mark.asyncio
async def test_saving_settings_pushes_them_to_every_endpoint_it_measures() -> None:
    """Saving connection settings re-pushes every target."""
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
    """An endpoint without a target reports ``measured: false``."""
    handler, _ = _handler(connections=[_connection()])
    view = await handler.get_target(TENANT, "support-kb")
    assert view.measured is False
    assert view.last_job is None


@pytest.mark.asyncio
async def test_the_endpoint_layer_lies_on_top_of_the_space_wide_one() -> None:
    """Endpoint settings override the connection's."""
    row = _connection(probe={"retrieval_top_k": 5, "similarity_threshold": 0.3})
    handler, client = _handler(connections=[row])
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(probe={"retrieval_top_k": 11})
    )
    sent = client.targets["support-kb"]["probe"]
    assert sent == {"retrieval_top_k": 11, "similarity_threshold": 0.3}


@pytest.mark.asyncio
async def test_the_collection_is_resolved_rather_than_typed() -> None:
    """The collection is resolved from the endpoint's dataset."""
    handler, client = _handler(connections=[_connection()])
    await handler.save_target(TENANT, "support-kb", TargetRequest())
    assert client.targets["support-kb"]["collection"] == "Collection_support_kb"


@pytest.mark.asyncio
async def test_a_collection_named_by_hand_wins_over_the_resolved_one() -> None:
    """An explicit collection overrides the resolved one."""
    handler, client = _handler(connections=[_connection()])
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(collection="Collection_legacy")
    )
    assert client.targets["support-kb"]["collection"] == "Collection_legacy"


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_block_saving() -> None:
    """A target is saved while the benchmark is down; ``synced_at`` stays empty."""
    handler, _ = _handler(client=_Client(reachable=False), connections=[_connection()])
    await handler.save_target(TENANT, "support-kb", TargetRequest())
    handler.targets.mark_synced.assert_not_called()  # type: ignore[attr-defined]
    handler.targets.create.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_measuring_needs_a_benchmark_to_be_connected_first() -> None:
    """Saving a target with no connection is refused with a reason."""
    handler, _ = _handler(connections=[])
    with pytest.raises(HTTPException) as refused:
        await handler.save_target(TENANT, "support-kb", TargetRequest())
    assert refused.value.status_code == 409
    assert "Connect one" in refused.value.detail


# --- runs -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_paused_endpoint_is_not_measured_on_request_either() -> None:
    """A paused target cannot be run."""
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
    """Settings are pushed before a run starts."""
    row = _connection(probe={"retrieval_top_k": 5})
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)
    await handler.start_run(TENANT, "support-kb", RunRequest(limit=2))
    assert client.targets["support-kb"]["probe"] == {"retrieval_top_k": 5}
    assert client.runs == [("support-kb", {"limit": 2, "defer_judging": False})]


@pytest.mark.asyncio
async def test_the_endpoint_layer_lies_on_top_of_the_space_wide_instrument() -> None:
    """Endpoint instrument settings override the connection's, field by field."""
    row = _connection(
        instrument={"judge_model": "gemma3-4b-gpu", "arms": ["open_book"]}
    )
    handler, client = _handler(connections=[row])
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(instrument={"judge_model": "gpt-4o"})
    )
    sent = client.targets["support-kb"]["instrument"]
    assert sent == {"judge_model": "gpt-4o", "arms": ["open_book"]}


@pytest.mark.asyncio
async def test_the_endpoint_instrument_round_trips_through_get_target() -> None:
    row = _connection(instrument={"judge_model": "gemma3-4b-gpu"})
    target = BenchmarkTarget(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        connection_id=row.id,
        instrument={"judge_model": "gpt-4o"},
    )
    handler, _ = _handler(connections=[row], target=target)
    view = await handler.get_target(TENANT, "support-kb")
    assert view.instrument == {"judge_model": "gpt-4o"}
    assert view.connection_instrument == {"judge_model": "gemma3-4b-gpu"}


@pytest.mark.asyncio
async def test_the_endpoint_page_gets_the_connections_capabilities_too() -> None:
    """The target response carries the connection's capabilities."""
    # A recent checked_at keeps _if_stale from refreshing the capabilities.
    row = _connection(
        capabilities={"generators": ["mcq", "qa"]},
        checked_at=datetime.now(timezone.utc),
    )
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(connections=[row], target=target)
    view = await handler.get_target(TENANT, "support-kb")
    assert view.capabilities["generators"] == ["mcq", "qa"]


# --- memory of the last run --------------------------------------------------


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_erase_the_last_run() -> None:
    """While the benchmark is down, the remembered job is shown."""
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
async def test_a_job_carries_its_progress_plan() -> None:
    plan = {"questions": 30, "models": ["a/m"], "passes": 2, "steps": 60}
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id,
        endpoint_id=ENDPOINT_ID,
        connection_id=row.id,
        last_job={
            "id": "live",
            "state": "running",
            "phase": "evaluate",
            "progress_plan": plan,
        },
    )
    handler, _ = _handler(
        client=_Client(reachable=False), connections=[row], target=target
    )
    [job] = await handler.list_jobs(TENANT, "support-kb")
    assert job.model_dump(mode="json")["progress_plan"] == plan


@pytest.mark.asyncio
async def test_a_run_the_benchmark_has_forgotten_leaves_the_page_too() -> None:
    """An empty job list clears the remembered job."""
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
    """The schedule is pushed to the benchmark, which runs it."""
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
    """``next_run_at`` comes from the benchmark."""
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
    """Without an answer from the benchmark, ``next_run_at`` is empty."""
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
    """The model catalogue is passed through unchanged."""
    connection = _connection()
    handler, client = _handler(connections=[connection])

    out = await handler.models(TENANT, connection.id, {"q": "claude", "limit": 0})

    assert out["models"][0]["id"] == "anthropic/claude-sonnet-5"
    assert out["pins"]
    assert out["fetched"]["openrouter"]
    assert client.asked_for_models["q"] == "claude"


def test_the_picker_filters_reach_the_benchmark() -> None:
    """Catalogue filters are forwarded to the benchmark."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from syft_space.components.benchmarks.routes import build_benchmark_routes
    from syft_space.components.tenants.dependency import get_tenant_dependency

    connection = _connection()
    handler, client = _handler(connections=[connection])
    app = FastAPI()
    app.include_router(build_benchmark_routes(handler))
    app.dependency_overrides[get_tenant_dependency] = lambda: TENANT

    answer = TestClient(app).get(
        f"/benchmarks/connections/{connection.id}/models",
        params={"web_search": "any", "lacks": "temperature"},
    )

    assert answer.status_code == 200, answer.text
    assert client.asked_for_models["web_search"] == "any"
    assert client.asked_for_models["lacks"] == "temperature"


@pytest.mark.asyncio
async def test_a_benchmark_that_is_down_does_not_look_like_an_empty_catalogue() -> None:
    """A failed catalogue call is an error, not an empty list."""
    connection = _connection()
    handler, _ = _handler(client=_Client(reachable=False), connections=[connection])

    with pytest.raises(HTTPException) as refusal:
        await handler.models(TENANT, connection.id, {})

    assert refusal.value.status_code == 502


@pytest.mark.asyncio
async def test_a_refused_refresh_keeps_the_benchmarks_own_words() -> None:
    """A refused refresh keeps the benchmark's status and detail."""
    connection = _connection()
    handler, _ = _handler(client=_Client(reachable=False), connections=[connection])

    with pytest.raises(HTTPException) as refusal:
        await handler.refresh_models(TENANT, connection.id)

    assert refusal.value.status_code == 403
    assert "external_hosts" in refusal.value.detail


# --- keeping the benchmark's description current ----------------------------


@pytest.mark.asyncio
async def test_a_stale_description_is_refreshed_when_the_page_opens() -> None:
    """An expired self-description is refreshed."""
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
    """A fresh self-description is not refetched."""
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
    """A naive ``checked_at`` from SQLite is read as UTC."""
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
    """A failed refresh keeps the cached description."""
    stale = _connection(fields={"instrument": [{"name": "judge_models"}]})
    handler, _ = _handler(client=_Client(reachable=False), connections=[stale])

    listed = await handler.list_connections(TENANT)

    assert listed[0].fields["instrument"][0]["name"] == "judge_models"
    assert listed[0].reachable is False


# --- the model providers ------------------------------------------------------


@pytest.mark.asyncio
async def test_the_provider_view_pairs_the_url_override_with_the_key_presence() -> None:
    row = _connection(defaults={"subject_url": "http://localhost:11434"})
    client = _Client()
    client.settings_values = {"subject_url": "https://openrouter.ai/api/v1"}
    client.credentials = {"subject_key": "sealed-already"}
    handler, _ = _handler(client=client, connections=[row])

    view = await handler.get_provider(TENANT, row.id)

    assert view.subject.url == "https://openrouter.ai/api/v1"
    assert view.subject.url_default == "http://localhost:11434"
    assert view.subject.key_set is True
    assert view.generator.key_set is False


@pytest.mark.asyncio
async def test_saving_provider_urls_reaches_the_benchmarks_settings() -> None:
    row = _connection()
    handler, client = _handler(connections=[row])

    await handler.save_provider(
        TENANT, row.id, ProviderUrls(subject_url="https://openrouter.ai/api/v1")
    )

    assert client.settings_values["subject_url"] == "https://openrouter.ai/api/v1"


@pytest.mark.asyncio
async def test_a_provider_key_is_sent_sealed_and_never_read_back() -> None:
    row = _connection()
    handler, client = _handler(connections=[row])

    view = await handler.save_provider_credential(
        TENANT, row.id, "subject_key", "sk-live-something"
    )

    assert client.credentials["subject_key"] == "sk-live-something"
    assert view.subject.key_set is True
    assert "sk-live-something" not in view.model_dump_json()


@pytest.mark.asyncio
async def test_an_unknown_credential_name_is_refused_before_it_reaches_the_benchmark() -> (
    None
):
    row = _connection()
    handler, client = _handler(connections=[row])

    with pytest.raises(HTTPException) as refused:
        await handler.save_provider_credential(TENANT, row.id, "database_url", "x")

    assert refused.value.status_code == 404
    assert client.credentials == {}


@pytest.mark.asyncio
async def test_clearing_a_provider_key_falls_back_to_the_shared_default() -> None:
    row = _connection()
    client = _Client()
    client.credentials = {"judge_key": "sk-old"}
    handler, _ = _handler(client=client, connections=[row])

    view = await handler.delete_provider_credential(TENANT, row.id, "judge_key")

    assert "judge_key" not in client.credentials
    assert view.judge.key_set is False


@pytest.mark.asyncio
async def test_the_web_check_is_a_provider_role_of_its_own() -> None:
    row = _connection()
    handler, client = _handler(connections=[row])

    await handler.save_provider(
        TENANT, row.id, ProviderUrls(filter_url="https://api.openai.com/v1")
    )
    view = await handler.save_provider_credential(
        TENANT, row.id, "filter_key", "sk-web"
    )

    assert client.settings_values["filter_url"] == "https://api.openai.com/v1"
    assert view.filter.url == "https://api.openai.com/v1"
    assert view.filter.key_set is True
    assert view.subject.key_set is False


# --- the console, embedded ----------------------------------------------------


def test_the_console_client_reaches_the_benchmark_by_its_url() -> None:
    handler = BenchmarkHandler(None, None, None, None, None)  # type: ignore[arg-type]
    row = _connection(url="http://benchmark:8200")

    client = handler._console_client(row, "session-token")

    assert client.url == "http://benchmark:8200"


@pytest.mark.asyncio
async def test_listing_pairs_mints_a_session_scoped_to_this_target() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)

    await handler.list_pairs(TENANT, "support-kb", {"status": "pending"})

    assert client.console_calls == [
        ("GET", "/console/pairs", None, {"status": "pending"})
    ]


@pytest.mark.asyncio
async def test_deleting_a_pair_proxies_through_the_console() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)

    await handler.delete_pair(TENANT, "support-kb", "pair-1")

    assert client.console_calls == [("DELETE", "/console/pairs/pair-1", None, {})]


@pytest.mark.asyncio
async def test_overriding_a_verdict_proxies_the_body_untouched() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)

    await handler.override_verdict(
        TENANT, "support-kb", "result-1", {"verdict": "correct", "reasoning": "checked"}
    )

    assert client.console_calls == [
        (
            "POST",
            "/console/results/result-1/verdict",
            {"verdict": "correct", "reasoning": "checked"},
            {},
        )
    ]


@pytest.mark.asyncio
async def test_a_console_call_a_paused_benchmark_refuses_surfaces_as_502() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(
        client=_Client(reachable=False), connections=[row], target=target
    )

    with pytest.raises(HTTPException) as refused:
        await handler.list_results(TENANT, "support-kb", {})

    assert refused.value.status_code == 502


# --- the benchmark refusing the settings themselves ---------------------------

CLASH = "Judge openai/gpt-5.1 and tested model openai/gpt-5.1 are from the same company"


class _StrictClient(_Client):
    """A benchmark that refuses a judge from a tested model's company with 422."""

    def __init__(self, *, refuse_run: bool = False) -> None:
        super().__init__()
        self.refuse_run = refuse_run

    async def put_target(self, key: str, spec: dict) -> Reply:
        if "openai/gpt-5.1" in (spec.get("instrument") or {}).get("subject_models", []):
            return Reply(ok=False, status=422, detail=CLASH)
        return await super().put_target(key, spec)

    async def start_run(self, key: str, request: dict) -> Reply:
        if self.refuse_run:
            return Reply(ok=False, status=422, detail=CLASH)
        return await super().start_run(key, request)


@pytest.mark.asyncio
async def test_a_refused_save_reaches_the_browser_and_is_not_stored() -> None:
    """The benchmark's 422 is passed on and the target is not stored."""
    handler, client = _handler(client=_StrictClient(), connections=[_connection()])
    with pytest.raises(HTTPException) as refused:
        await handler.save_target(
            TENANT,
            "support-kb",
            TargetRequest(instrument={"subject_models": ["openai/gpt-5.1"]}),
        )
    assert refused.value.status_code == 422
    assert refused.value.detail == CLASH
    handler.targets.create.assert_not_called()  # type: ignore[attr-defined]
    assert client.targets == {}


@pytest.mark.asyncio
async def test_a_refused_push_before_a_run_reaches_the_browser() -> None:
    row = _connection(instrument={"subject_models": ["openai/gpt-5.1"]})
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(client=_StrictClient(), connections=[row], target=target)
    with pytest.raises(HTTPException) as refused:
        await handler.start_run(TENANT, "support-kb", RunRequest())
    assert refused.value.status_code == 422
    assert refused.value.detail == CLASH
    assert client.runs == []


@pytest.mark.asyncio
async def test_a_refused_run_reaches_the_browser_as_422_not_502() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(
        client=_StrictClient(refuse_run=True), connections=[row], target=target
    )
    with pytest.raises(HTTPException) as refused:
        await handler.start_run(TENANT, "support-kb", RunRequest())
    assert refused.value.status_code == 422
    assert refused.value.detail == CLASH


@pytest.mark.asyncio
async def test_the_web_check_model_reaches_the_benchmark_untouched() -> None:
    handler, client = _handler(connections=[_connection()])
    await handler.save_target(
        TENANT,
        "support-kb",
        TargetRequest(instrument={"filter_model": "openai/gpt-5.1"}),
    )
    assert client.targets["support-kb"]["instrument"] == {
        "filter_model": "openai/gpt-5.1"
    }
    handler.targets.mark_synced.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_the_web_search_settings_reach_the_benchmark_untouched() -> None:
    handler, client = _handler(connections=[_connection()])
    instrument = {
        "web_search_engine": "plugin",
        "web_search_closed_book": True,
        "web_search_with_context": True,
        "web_search_generator": False,
        "web_search_judge": False,
        "web_search_max_results": 7,
        "filter_judge_model": "anthropic/claude-opus-5",
    }
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(instrument=instrument)
    )
    assert client.targets["support-kb"]["instrument"] == instrument


def test_a_validation_refusal_reads_as_field_and_reason() -> None:
    import httpx

    from syft_space.components.benchmarks.client import _detail

    resp = httpx.Response(
        422,
        json={
            "detail": [
                {"loc": ["body", "instrument", "arms"], "msg": "bad arm"},
            ]
        },
    )
    assert _detail(resp) == "instrument.arms: bad arm"


# --- the time window ----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_window_count_is_the_benchmarks_not_computed_here() -> None:
    """The window count comes from the benchmark."""
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(connections=[row], target=target)

    counted = await handler.window(TENANT, "support-kb", 2)

    assert client.window_asks == ("support-kb", 2)
    assert (counted.count, counted.undated, counted.total) == (4, 1, 9)
    assert counted.window_days == 2


@pytest.mark.asyncio
async def test_a_benchmark_that_cannot_count_is_a_bad_gateway() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, _ = _handler(
        client=_Client(reachable=False), connections=[row], target=target
    )

    with pytest.raises(HTTPException) as refused:
        await handler.window(TENANT, "support-kb")
    assert refused.value.status_code == 502


# --- the mandatory web check ---------------------------------------------------

NO_WEB_CHECK = "Choose a web check model"


class _UnfilteredClient(_Client):
    """A benchmark that refuses a launch or a scheduled save without a web check model."""

    async def put_target(self, key: str, spec: dict) -> Reply:
        if spec.get("schedule") and not (spec.get("instrument") or {}).get(
            "filter_model"
        ):
            return Reply(ok=False, status=422, detail=NO_WEB_CHECK)
        return await super().put_target(key, spec)

    async def start_run(self, key: str, request: dict) -> Reply:
        return Reply(ok=False, status=422, detail=NO_WEB_CHECK)


@pytest.mark.asyncio
async def test_a_run_without_a_web_check_model_reaches_the_browser_as_422() -> None:
    row = _connection()
    target = BenchmarkTarget(
        tenant_id=TENANT.id, endpoint_id=ENDPOINT_ID, connection_id=row.id
    )
    handler, client = _handler(
        client=_UnfilteredClient(), connections=[row], target=target
    )
    with pytest.raises(HTTPException) as refused:
        await handler.start_run(TENANT, "support-kb", RunRequest())
    assert refused.value.status_code == 422
    assert refused.value.detail == NO_WEB_CHECK
    assert client.runs == []


@pytest.mark.asyncio
async def test_a_scheduled_save_without_a_web_check_model_reaches_the_browser() -> None:
    handler, client = _handler(client=_UnfilteredClient(), connections=[_connection()])
    with pytest.raises(HTTPException) as refused:
        await handler.save_target(TENANT, "support-kb", TargetRequest(schedule="24h"))
    assert refused.value.status_code == 422
    assert refused.value.detail == NO_WEB_CHECK
    assert client.targets == {}


@pytest.mark.asyncio
async def test_the_new_run_settings_reach_the_benchmark_untouched() -> None:
    handler, client = _handler(connections=[_connection()])
    instrument = {"concurrency": 24, "manual_status_priority": "manual"}
    await handler.save_target(
        TENANT, "support-kb", TargetRequest(instrument=instrument)
    )
    assert client.targets["support-kb"]["instrument"] == instrument
