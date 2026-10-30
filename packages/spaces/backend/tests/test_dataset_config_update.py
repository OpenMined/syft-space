"""Editing a dataset's configuration: merge rules, persistence, the change
event and its listeners, and the dry-run healthcheck.

Uses the real repositories on a temporary SQLite database and the real
bindings; only the network-facing calls (feed validation, Weaviate
healthcheck, client eviction) are stubbed.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException

from syft_space.components.dataset_types import register_builtin_types
from syft_space.components.dataset_types.registry import DATASET_TYPE_REGISTRY
from syft_space.components.datasets.entities import Dataset
from syft_space.components.datasets.events import (
    AxisChange,
    DatasetConfigurationChanged,
)
from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.datasets.provisioner_state_repository import (
    ProvisionerStateRepository,
)
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.datasets.schemas import (
    HealthcheckRequest,
    UpdateDatasetRequest,
)
from syft_space.components.datasets.selection_repository import (
    DatasetSelectionRepository,
)
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.shared import client_cache
from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.sources.rss.rss_source import RssProvider
from syft_space.components.vector_stores.config_change import ClientCacheEvictor
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)


@pytest.fixture(scope="module", autouse=True)
def builtin_types():
    """Responses redact through the global registry, so it must know the types."""
    if not DATASET_TYPE_REGISTRY.is_dataset_type_registered("rss"):
        register_builtin_types(DATASET_TYPE_REGISTRY)
    return DATASET_TYPE_REGISTRY


WEAVIATE_CONF = {
    "http_url": "http://weaviate.example:8080",
    "grpc_url": "http://weaviate.example:50051",
    "api_key": "old-key",
    "collection_name": "Docs",
    "headers": {"X-Cohere-Api-Key": "cohere", "X-OpenAI-Api-Key": "openai"},
    "content_property": "body",
}


class _Recorder:
    """A listener that keeps every event it is told about."""

    def __init__(self) -> None:
        self.events: list[DatasetConfigurationChanged] = []

    async def on_configuration_changed(self, event) -> None:
        self.events.append(event)


class _Failing:
    async def on_configuration_changed(self, event) -> None:
        raise RuntimeError("listener broke")


@pytest_asyncio.fixture
async def dataset_repository(main_db) -> DatasetRepository:
    return DatasetRepository(main_db)


@pytest_asyncio.fixture
async def recorder() -> _Recorder:
    return _Recorder()


@pytest_asyncio.fixture
async def handler(main_db, endpoint_repository, dataset_repository, recorder):
    return DatasetHandler(
        DATASET_TYPE_REGISTRY,
        dataset_repository,
        ProvisionerStateRepository(main_db),
        endpoint_repository=endpoint_repository,
        selection_repository=DatasetSelectionRepository(main_db),
        configuration_listeners=[_Failing(), recorder],
    )


@pytest_asyncio.fixture
async def weaviate_dataset(dataset_repository, tenant) -> Dataset:
    return await dataset_repository.create(
        Dataset(
            tenant_id=tenant.id,
            name="docs",
            dtype="remote_weaviate",
            configuration=dict(WEAVIATE_CONF),
        )
    )


async def _stored(dataset_repository, tenant, name="docs") -> dict[str, Any]:
    row = await dataset_repository.get_by_name(name, tenant.id)
    assert row is not None
    return row.configuration


async def _update(handler, tenant, configuration, name="docs"):
    return await handler.update_dataset(
        name, UpdateDatasetRequest(configuration=configuration), tenant
    )


# ── Merge rules ──────────────────────────────────────────────────────────


class TestMergeRules:
    async def test_a_locked_key_is_refused_by_name(
        self, handler, tenant, weaviate_dataset, dataset_repository
    ):
        with pytest.raises(HTTPException) as exc:
            await _update(handler, tenant, {"collection_name": "Other"})
        assert exc.value.status_code == 400
        assert "collection_name" in exc.value.detail
        assert (await _stored(dataset_repository, tenant)) == WEAVIATE_CONF

    async def test_a_scalar_replaces_and_absent_keys_keep(
        self, handler, tenant, weaviate_dataset, dataset_repository
    ):
        response = await _update(
            handler, tenant, {"content_property": "text", "api_key": "new-key"}
        )
        stored = await _stored(dataset_repository, tenant)
        assert stored["content_property"] == "text"
        assert stored["api_key"] == "new-key"
        assert stored["headers"] == WEAVIATE_CONF["headers"]  # untouched
        # The response is redacted like every other read.
        assert "api_key" not in response.configuration
        assert response.configuration["headers"] == {
            "X-Cohere-Api-Key": None,
            "X-OpenAI-Api-Key": None,
        }

    async def test_null_removes_a_key(
        self, handler, tenant, weaviate_dataset, dataset_repository
    ):
        await _update(handler, tenant, {"content_property": None})
        assert "content_property" not in await _stored(dataset_repository, tenant)

    async def test_a_secret_dict_is_merged_per_entry(
        self, handler, tenant, weaviate_dataset, dataset_repository
    ):
        """null keeps the stored value, a string replaces it, absent removes it."""
        await _update(
            handler,
            tenant,
            {"headers": {"X-Cohere-Api-Key": None, "X-Voyage-Api-Key": "voyage"}},
        )
        assert (await _stored(dataset_repository, tenant))["headers"] == {
            "X-Cohere-Api-Key": "cohere",
            "X-Voyage-Api-Key": "voyage",
        }

    async def test_a_refused_merge_writes_nothing(
        self, handler, tenant, weaviate_dataset, dataset_repository
    ):
        with pytest.raises(HTTPException) as exc:
            await _update(handler, tenant, {"http_url": "not a url"})
        assert exc.value.status_code == 422
        assert (await _stored(dataset_repository, tenant)) == WEAVIATE_CONF

    async def test_other_fields_still_update_alone(
        self, handler, tenant, weaviate_dataset, dataset_repository, recorder
    ):
        response = await handler.update_dataset(
            "docs", UpdateDatasetRequest(summary="renamed"), tenant
        )
        assert response.summary == "renamed"
        assert (await _stored(dataset_repository, tenant)) == WEAVIATE_CONF
        assert recorder.events == []

    async def test_a_row_with_python_names_is_canonicalised(
        self, handler, tenant, dataset_repository, monkeypatch, recorder
    ):
        """One edit leaves one spelling per key, never both."""

        async def accept(cls, configuration):
            return None

        monkeypatch.setattr(RssProvider, "validate_configuration", classmethod(accept))
        await dataset_repository.create(
            Dataset(
                tenant_id=tenant.id,
                name="feeds",
                dtype="rss",
                configuration={
                    "feed_urls": "https://a.example/feed",
                    "collection_name": "feeds",
                    "http_port": 8123,
                },
            )
        )
        await _update(
            handler, tenant, {"feedUrls": "https://b.example/feed"}, name="feeds"
        )
        assert (await _stored(dataset_repository, tenant, "feeds")) == {
            "feedUrls": "https://b.example/feed",
            "collectionName": "feeds",
            "httpPort": 8123,
        }
        assert recorder.events[-1].source.changed
        assert not recorder.events[-1].vector_store.changed


# ── The change event ─────────────────────────────────────────────────────


class TestChangeEvent:
    async def test_published_after_commit_with_both_halves(
        self, handler, tenant, weaviate_dataset, dataset_repository, recorder
    ):
        await _update(handler, tenant, {"api_key": "new-key"})
        (event,) = recorder.events
        assert event.dataset.name == "docs"
        assert event.vector_store.old["api_key"] == "old-key"
        assert event.vector_store.new["api_key"] == "new-key"
        assert event.vector_store.changed and not event.source.changed
        assert event.vector_store_cls is WeaviateVectorStore
        # Committed first: a listener re-reading the row sees the new value.
        assert (await _stored(dataset_repository, tenant))["api_key"] == "new-key"

    async def test_an_unchanged_configuration_publishes_nothing(
        self, handler, tenant, weaviate_dataset, recorder
    ):
        await _update(handler, tenant, {"content_property": "body"})
        assert recorder.events == []

    async def test_a_failing_listener_does_not_stop_the_others(
        self, handler, tenant, weaviate_dataset, recorder
    ):
        """The fixture lists a failing listener before the recorder."""
        await _update(handler, tenant, {"api_key": "new-key"})
        assert len(recorder.events) == 1


# ── Listeners ────────────────────────────────────────────────────────────


def _event(old: dict[str, Any], new: dict[str, Any], **axis) -> Any:
    dataset = Dataset(
        tenant_id=__import__("uuid").uuid4(),
        name="docs",
        dtype="remote_weaviate",
        configuration=new,
    )
    source = axis.get("source", AxisChange({}, {}))
    return DatasetConfigurationChanged(
        dataset=dataset,
        source=source,
        vector_store=AxisChange(old, new),
        vector_store_cls=WeaviateVectorStore,
    )


class TestClientCacheEvictor:
    async def test_evicts_the_old_connection(self, monkeypatch):
        evicted: list[tuple[str, tuple]] = []

        async def evict(namespace, key):
            evicted.append((namespace, key))

        monkeypatch.setattr(client_cache, "evict", evict)
        old = dict(WEAVIATE_CONF)
        new = {**WEAVIATE_CONF, "api_key": "new-key"}
        await ClientCacheEvictor().on_configuration_changed(_event(old, new))
        assert evicted == [
            (WeaviateVectorStore.NAME, WeaviateVectorStore(old).client_key())
        ]

    async def test_a_non_connection_edit_keeps_the_client(self, monkeypatch):
        async def evict(namespace, key):
            raise AssertionError("should not evict")

        monkeypatch.setattr(client_cache, "evict", evict)
        new = {**WEAVIATE_CONF, "content_property": "text"}
        await ClientCacheEvictor().on_configuration_changed(
            _event(dict(WEAVIATE_CONF), new)
        )


class TestIngestionListener:
    @pytest_asyncio.fixture
    async def manager(self, main_db, dataset_repository, monkeypatch):
        restarted: list[Any] = []

        async def restart(self, dataset_id, tenant_id):
            restarted.append(dataset_id)

        monkeypatch.setattr(IngestionManager, "restart_dataset_ingestion", restart)
        manager = IngestionManager(
            dataset_repository=dataset_repository,
            ingestion_repository=IngestionJobRepository(main_db),
            selection_repository=DatasetSelectionRepository(main_db),
            registry=DATASET_TYPE_REGISTRY,
        )
        return manager, restarted

    async def test_restarts_the_stream_when_the_source_changed(self, manager):
        manager, restarted = manager
        event = _event({}, {}, source=AxisChange({"feedUrls": "a"}, {"feedUrls": "b"}))
        await manager.on_configuration_changed(event)
        assert restarted == [event.dataset.id]

    async def test_leaves_the_stream_alone_for_a_store_edit(self, manager):
        manager, restarted = manager
        await manager.on_configuration_changed(
            _event(dict(WEAVIATE_CONF), {**WEAVIATE_CONF, "api_key": "k"})
        )
        assert restarted == []


# ── Dry-run healthcheck ──────────────────────────────────────────────────


class TestDryRunHealthcheck:
    async def test_checks_the_merged_configuration_and_persists_nothing(
        self, handler, tenant, weaviate_dataset, dataset_repository, monkeypatch
    ):
        seen: list[str] = []

        async def healthcheck(self):
            seen.append(self.config.api_key)
            return HealthcheckResponse(status=HealthcheckStatus.HEALTHY, message="ok")

        monkeypatch.setattr(WeaviateVectorStore, "healthcheck", healthcheck)
        result = await handler.healthcheck_with(
            "docs", HealthcheckRequest(configuration={"api_key": "candidate"}), tenant
        )
        assert result.status == HealthcheckStatus.HEALTHY
        assert seen == ["candidate"]
        assert (await _stored(dataset_repository, tenant))["api_key"] == "old-key"

    async def test_a_failing_connection_reports_unhealthy(
        self, handler, tenant, weaviate_dataset, monkeypatch
    ):
        async def healthcheck(self):
            raise ConnectionError("refused")

        monkeypatch.setattr(WeaviateVectorStore, "healthcheck", healthcheck)
        result = await handler.healthcheck_with(
            "docs", HealthcheckRequest(configuration={}), tenant
        )
        assert result.status == HealthcheckStatus.UNHEALTHY
        assert "refused" in result.message

    async def test_the_same_merge_rules_apply(self, handler, tenant, weaviate_dataset):
        with pytest.raises(HTTPException) as exc:
            await handler.healthcheck_with(
                "docs", HealthcheckRequest(configuration={"filters": None}), tenant
            )
        assert exc.value.status_code == 400
