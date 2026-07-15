"""ChromaDB connection settings (``SYFT_CHROMADB_*``): config-sourced
defaults, provisioner resolution, and the external provisioner."""

from __future__ import annotations

import pytest

from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as store_module,
)
from syft_space.components.vector_stores.chromadb_local import external_provisioner
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
    _resolve_provisioner_cls,
)
from syft_space.components.vector_stores.chromadb_local.external_provisioner import (
    ExternalChromaDBProvisioner,
)
from syft_space.components.vector_stores.chromadb_local.provisioner import (
    LocalChromaDBProvisioner,
)
from syft_space.components.vector_stores.chromadb_local.schemas import (
    ChromaDBLocalVectorStoreConfiguration,
)
from syft_space.config import app_settings

# ============== Provisioner resolution ==============


def test_provision_flag_default_keeps_subprocess_provisioner():
    assert app_settings.chromadb_provision is True
    assert ChromaDBLocalVectorStore.PROVISIONER_CLS is LocalChromaDBProvisioner


def test_provision_true_resolves_subprocess_provisioner(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_provision", True)
    assert _resolve_provisioner_cls() is LocalChromaDBProvisioner


def test_provision_false_resolves_external_provisioner(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_provision", False)
    assert _resolve_provisioner_cls() is ExternalChromaDBProvisioner


# ============== Port default flows from config ==============


def test_http_port_defaults_from_settings(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_http_port", 9200)
    config = ChromaDBLocalVectorStoreConfiguration(collectionName="docs")
    assert config.http_port == 9200


def test_http_port_explicit_value_wins(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_http_port", 9200)
    config = ChromaDBLocalVectorStoreConfiguration(collectionName="docs", httpPort=8123)
    assert config.http_port == 8123


# ============== Host / client targeting ==============


def test_host_comes_from_settings(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_host", "chroma.cluster.svc")
    assert ChromaDBLocalVectorStore.host() == "chroma.cluster.svc"


class _FakeChromaModule:
    """Captures AsyncHttpClient kwargs in place of the real chromadb."""

    def __init__(self):
        self.calls: list[dict] = []

    async def AsyncHttpClient(self, **kwargs):  # noqa: N802 - mirrors chromadb
        self.calls.append(kwargs)
        return object()


async def test_get_client_uses_configured_connection(monkeypatch):
    monkeypatch.setattr(app_settings, "chromadb_host", "chroma.cluster.svc")
    monkeypatch.setattr(app_settings, "chromadb_http_port", 8000)
    monkeypatch.setattr(app_settings, "chromadb_database", "space_research_lab")
    monkeypatch.setattr(app_settings, "chromadb_ssl", False)
    fake = _FakeChromaModule()
    monkeypatch.setattr(store_module, "_import_chromadb", lambda: fake)

    store = ChromaDBLocalVectorStore({"collectionName": "docs"})
    await store.get_client()

    assert fake.calls == [
        {
            "host": "chroma.cluster.svc",
            "port": 8000,
            "ssl": False,
            "database": "space_research_lab",
        }
    ]


async def test_get_client_defaults_match_local_subprocess(monkeypatch):
    fake = _FakeChromaModule()
    monkeypatch.setattr(store_module, "_import_chromadb", lambda: fake)

    store = ChromaDBLocalVectorStore({"collectionName": "docs"})
    await store.get_client()

    assert fake.calls == [
        {
            "host": "localhost",
            "port": 8100,
            "ssl": False,
            "database": "default_database",
        }
    ]


# ============== External provisioner ==============


class _FakeAdmin:
    def __init__(self, existing: bool, create_error: Exception | None = None):
        self.existing = existing
        self.create_error = create_error
        self.created: list[str] = []

    async def get_database(self, name):
        if not self.existing:
            raise ValueError(f"Database {name} does not exist")

    async def create_database(self, name):
        if self.create_error is not None:
            raise self.create_error
        self.created.append(name)


async def test_start_creates_database_when_missing(monkeypatch):
    admin = _FakeAdmin(existing=False)
    monkeypatch.setattr(external_provisioner, "_build_admin_client", lambda: admin)
    monkeypatch.setattr(app_settings, "chromadb_host", "chroma")
    monkeypatch.setattr(app_settings, "chromadb_http_port", 8000)
    monkeypatch.setattr(app_settings, "chromadb_database", "space_a")

    state = await ExternalChromaDBProvisioner.start({})

    assert admin.created == ["space_a"]
    assert state == {"host": "chroma", "httpPort": 8000, "database": "space_a"}


async def test_start_noop_when_database_present(monkeypatch):
    admin = _FakeAdmin(existing=True)
    monkeypatch.setattr(external_provisioner, "_build_admin_client", lambda: admin)

    await ExternalChromaDBProvisioner.start({})

    assert admin.created == []


async def test_start_tolerates_concurrent_create(monkeypatch):
    admin = _FakeAdmin(
        existing=False, create_error=ValueError("Database space_a already exists")
    )
    monkeypatch.setattr(external_provisioner, "_build_admin_client", lambda: admin)
    monkeypatch.setattr(app_settings, "chromadb_database", "space_a")

    await ExternalChromaDBProvisioner.start({})  # must not raise


async def test_start_raises_when_unreachable(monkeypatch):
    admin = _FakeAdmin(
        existing=False, create_error=ConnectionError("connection refused")
    )
    monkeypatch.setattr(external_provisioner, "_build_admin_client", lambda: admin)

    with pytest.raises(RuntimeError, match="unavailable"):
        await ExternalChromaDBProvisioner.start({})


async def test_running_and_status_follow_heartbeat(monkeypatch):
    async def _up():
        return True

    async def _down():
        return False

    monkeypatch.setattr(external_provisioner, "_heartbeat", _up)
    assert await ExternalChromaDBProvisioner.is_running({}) is True
    assert await ExternalChromaDBProvisioner.status({}) == "running"
    await ExternalChromaDBProvisioner.wait_until_ready({})  # must not raise

    monkeypatch.setattr(external_provisioner, "_heartbeat", _down)
    assert await ExternalChromaDBProvisioner.is_running({}) is False
    assert await ExternalChromaDBProvisioner.status({}) == "stopped"
    with pytest.raises(TimeoutError):
        await ExternalChromaDBProvisioner.wait_until_ready({})
