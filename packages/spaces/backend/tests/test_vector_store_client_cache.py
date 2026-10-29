"""Vector stores reuse one connected client per connection config.

Store instances are rebuilt per request, so the client cache lives at
module level and is keyed by the connection fields, not the instance.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field, SecretStr

from syft_space.components.shared import client_cache
from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as chroma_module,
)
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)
from syft_space.components.vector_stores.weaviate_remote import (
    weaviate_vector_store as ws_module,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

WEAVIATE_CONFIG = {
    "http_url": "https://weaviate.example.com:8443",
    "grpc_url": "https://weaviate.example.com:50051",
    "api_key": "secret",
    "collection_name": "Docs",
}


class FakeWeaviateClient:
    instances: list[FakeWeaviateClient] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connected = False
        self.closed = False
        FakeWeaviateClient.instances.append(self)

    async def connect(self):
        self.connected = True

    async def close(self):
        self.closed = True


class FakeWeaviateError(Exception):
    """Stands in for WeaviateBaseError."""


class FakeInvalidInputError(FakeWeaviateError):
    """Stands in for WeaviateInvalidInputError."""


class FakeGRPCUnavailableError(FakeWeaviateError):
    """Any other subclass: the kind a dead connection surfaces as."""


@pytest.fixture
def fake_weaviate(monkeypatch):
    """Stand in for every name the store takes from ``weaviate``.

    ``raising=False`` because CI runs without the optional package, so the
    store module has none of these attributes there.
    """
    FakeWeaviateClient.instances = []
    stubs = {
        "enabled": True,
        "weaviate": SimpleNamespace(use_async_with_custom=FakeWeaviateClient),
        "Auth": SimpleNamespace(api_key=lambda key: ("api_key", key)),
        "AdditionalConfig": lambda timeout: SimpleNamespace(timeout=timeout),
        "Timeout": lambda init: SimpleNamespace(init=init),
        "MetadataQuery": lambda **kwargs: kwargs,
        "WeaviateBaseError": FakeWeaviateError,
        "WeaviateInvalidInputError": FakeInvalidInputError,
    }
    for name, value in stubs.items():
        monkeypatch.setattr(ws_module, name, value, raising=False)
    return FakeWeaviateClient


# ── key_from ────────────────────────────────────────────────────────────


def test_key_from_uses_alias_names_and_freezes_nested_values():
    class Cfg(BaseModel):
        http_port: int = Field(alias="httpPort")
        headers: dict[str, str] | None = None
        tags: list[str] = []
        model_config = {"populate_by_name": True}

    cfg = Cfg(httpPort=8100, headers={"b": "2", "a": "1"}, tags=["x"])

    key = client_cache.key_from(cfg, ["httpPort", "headers", "tags", "missing"])

    assert key == (8100, (("a", "1"), ("b", "2")), ("x",), None)
    hash(key)


def test_key_from_compares_urls_by_value():
    make = ws_module.RemoteWeaviateVectorStoreConfiguration.model_validate

    same = client_cache.key_from(make(WEAVIATE_CONFIG), ["http_url"])
    again = client_cache.key_from(make(dict(WEAVIATE_CONFIG)), ["http_url"])
    other = client_cache.key_from(
        make({**WEAVIATE_CONFIG, "http_url": "https://other.example.com"}),
        ["http_url"],
    )

    assert same == again and hash(same) == hash(again)
    assert same != other
    assert str(same[0]) == "https://weaviate.example.com:8443/"


def test_key_from_keeps_secret_values_distinct_but_masked():
    """A JSON dump would turn every SecretStr into asterisks and collide."""

    class Cfg(BaseModel):
        api_key: SecretStr

    k1 = client_cache.key_from(Cfg(api_key="one"), ["api_key"])
    k2 = client_cache.key_from(Cfg(api_key="two"), ["api_key"])
    k1_again = client_cache.key_from(Cfg(api_key="one"), ["api_key"])

    assert k1 != k2
    assert k1 == k1_again and hash(k1) == hash(k1_again)
    assert "one" not in repr(k1)  # safe if a key ever reaches a log line


# ── Weaviate ────────────────────────────────────────────────────────────


async def test_weaviate_instances_with_same_connection_share_one_client(
    fake_weaviate,
):
    a = await WeaviateVectorStore(WEAVIATE_CONFIG).get_client()
    b = await WeaviateVectorStore(
        {**WEAVIATE_CONFIG, "collection_name": "X"}
    ).get_client()

    assert a is b
    assert len(fake_weaviate.instances) == 1
    assert a.connected


async def test_weaviate_connect_uses_a_longer_init_timeout(fake_weaviate):
    client = await WeaviateVectorStore(WEAVIATE_CONFIG).get_client()

    timeout = client.kwargs["additional_config"].timeout
    assert timeout.init == WeaviateVectorStore.CONNECT_TIMEOUT


@pytest.mark.parametrize(
    "change",
    [
        {"api_key": "rotated"},
        {"http_url": "https://other.example.com"},
        {"headers": {"X-OpenAI-Api-Key": "k"}},
    ],
)
async def test_weaviate_connection_change_is_a_new_client(fake_weaviate, change):
    a = await WeaviateVectorStore(WEAVIATE_CONFIG).get_client()
    b = await WeaviateVectorStore({**WEAVIATE_CONFIG, **change}).get_client()

    assert a is not b
    assert len(fake_weaviate.instances) == 2


def _failing_collection(error: Exception):
    async def near_text(**kwargs):
        raise error

    return SimpleNamespace(query=SimpleNamespace(near_text=near_text))


@pytest.mark.parametrize(
    "error",
    [FakeWeaviateError("connection lost"), FakeGRPCUnavailableError("channel down")],
)
async def test_weaviate_search_evicts_the_client_on_weaviate_errors(
    fake_weaviate, error
):
    store = WeaviateVectorStore(WEAVIATE_CONFIG)
    first = await store.get_client()
    first.collections = SimpleNamespace(get=lambda name: _failing_collection(error))

    with pytest.raises(type(error)):
        await store.search(SimpleNamespace(), "q")

    assert first.closed
    assert await store.get_client() is not first


async def test_weaviate_search_keeps_the_client_on_invalid_input(fake_weaviate):
    store = WeaviateVectorStore(WEAVIATE_CONFIG)
    first = await store.get_client()
    first.collections = SimpleNamespace(
        get=lambda name: _failing_collection(FakeInvalidInputError("bad filter"))
    )

    with pytest.raises(FakeInvalidInputError):
        await store.search(SimpleNamespace(), "q")

    assert not first.closed
    assert await store.get_client() is first


async def test_close_all_closes_weaviate_clients(fake_weaviate):
    client = await WeaviateVectorStore(WEAVIATE_CONFIG).get_client()

    await client_cache.close_all()

    assert client.closed
    assert await WeaviateVectorStore(WEAVIATE_CONFIG).get_client() is not client


# ── ChromaDB ────────────────────────────────────────────────────────────


class _FakeChromaModule:
    def __init__(self):
        self.calls = 0

    async def AsyncHttpClient(self, **kwargs):  # noqa: N802 - mirrors chromadb
        self.calls += 1
        return object()


async def test_chromadb_instances_share_one_client(monkeypatch):
    fake = _FakeChromaModule()
    monkeypatch.setattr(chroma_module, "_import_chromadb", lambda: fake)

    a = await ChromaDBLocalVectorStore({"collectionName": "a"}).get_client()
    b = await ChromaDBLocalVectorStore({"collectionName": "b"}).get_client()

    assert a is b
    assert fake.calls == 1


def test_chromadb_embedding_model_is_built_once_per_process(monkeypatch):
    built = 0

    class FakeEmbeddingFn:
        def __init__(self):
            nonlocal built
            built += 1

        def __call__(self, texts):
            return [[0.0] for _ in texts]

    monkeypatch.setattr(chroma_module, "_import_embedding_fn", lambda: FakeEmbeddingFn)
    monkeypatch.setattr(ChromaDBLocalVectorStore, "_embedding_fn", None)

    ChromaDBLocalVectorStore({"collectionName": "a"})._generate_embeddings(["x"])
    ChromaDBLocalVectorStore({"collectionName": "b"})._generate_embeddings(["y"])

    assert built == 1
