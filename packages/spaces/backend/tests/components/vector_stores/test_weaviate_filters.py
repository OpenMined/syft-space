"""Weaviate: the shared tree translated to ``Filter`` calls, the owner's
stored configuration still loading, and property types read from the
collection for ``filter_schema``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest
from pydantic import TypeAdapter

from syft_space.components.shared import client_cache
from syft_space.components.shared.filter_types import (
    FieldFilterSpec,
    FilterNode,
    FilterOperator,
    FilterValueDtype,
    ops_for,
)
from syft_space.components.shared.metadata_types import DatasetMetadata, MetadataType
from syft_space.components.vector_stores.weaviate_remote.filters import (
    build_filter_node,
)
from syft_space.components.vector_stores.weaviate_remote.schemas import (
    RemoteWeaviateVectorStoreConfiguration,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateMetadataFields,
    WeaviateVectorStore,
)

NODE = TypeAdapter(FilterNode)


# ============== translation: a recording stand-in for ``Filter`` ==============


class _Target:
    """What ``Filter.by_property(...)`` / ``by_creation_time()`` return."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __getattr__(self, method: str):
        return lambda value: (self.name, method, value)


class _Filter:
    @staticmethod
    def by_property(name: str) -> _Target:
        return _Target(name)

    @staticmethod
    def by_creation_time() -> _Target:
        return _Target("<creation_time>")

    @staticmethod
    def all_of(items: list[Any]) -> tuple:
        return ("all_of", items)

    @staticmethod
    def any_of(items: list[Any]) -> tuple:
        return ("any_of", items)

    @staticmethod
    def not_(item: Any) -> tuple:
        return ("not", item)


def _build(node: dict) -> Any:
    return build_filter_node(NODE.validate_python(node), _Filter)


def test_in_is_contains_any_on_the_property():
    built = _build(
        {"type": "condition", "field": "status", "op": "in", "value": ["a", "b"]}
    )
    assert built == ("status", "contains_any", ["a", "b"])


def test_nin_is_the_negation_of_contains_any():
    built = _build(
        {"type": "condition", "field": "status", "op": "nin", "value": ["a"]}
    )
    assert built == ("not", ("status", "contains_any", ["a"]))


def test_creation_time_targets_the_object_timestamp_not_a_property():
    built = _build(
        {
            "type": "condition",
            "field": "creation_time",
            "op": "gte",
            "value": "2024-01-01",
        }
    )
    assert built == ("<creation_time>", "greater_or_equal", "2024-01-01")


def test_groups_nest_to_the_cap():
    node: dict = {"type": "condition", "field": "f", "op": "eq", "value": 1}
    for op in ("and", "or", "and", "or", "and"):
        node = {"type": "group", "op": op, "operands": [node]}
    built = _build(node)
    assert built == (
        "all_of",
        [("any_of", [("all_of", [("any_of", [("all_of", [("f", "equal", 1)])])])])],
    )


# ============== the owner's stored configuration ==============


def _config(**overrides: Any) -> RemoteWeaviateVectorStoreConfiguration:
    return RemoteWeaviateVectorStoreConfiguration.model_validate(
        {
            "http_url": "http://w.test:8080",
            "grpc_url": "http://w.test:50051",
            "api_key": "k",
            "collection_name": "C",
            **overrides,
        }
    )


def test_a_stored_filter_with_property_and_no_dtype_loads_as_before():
    """What the form stored before ``field`` existed: coerced as a string."""
    cfg = _config(
        filters={
            "type": "group",
            "op": "and",
            "operands": [
                {"type": "condition", "property": "status", "op": "eq", "value": 1},
                {
                    "type": "group",
                    "op": "or",
                    "operands": [
                        {
                            "type": "condition",
                            "property": "n",
                            "op": "in",
                            "value": "1, 2",
                        }
                    ],
                },
            ],
        }
    )
    first, inner = cfg.filters.operands
    assert first.field == "status"
    assert first.value_dtype is FilterValueDtype.STRING
    assert first.value == "1"
    assert inner.operands[0].value == ["1", "2"]


def test_a_stored_dtype_is_kept():
    cfg = _config(
        filters={
            "type": "condition",
            "property": "n",
            "op": "gt",
            "value_dtype": "numeric",
            "value": "3",
        }
    )
    assert cfg.filters.value == 3


def test_the_configuration_schema_names_field_not_property():
    props = WeaviateVectorStore.configuration_schema()["$defs"]["FilterCondition"][
        "properties"
    ]
    assert "field" in props and "property" not in props


# ============== filter_schema: types from the collection ==============


class _DataType(Enum):
    TEXT = "text"
    INT = "int"
    DATE = "date"
    TEXT_ARRAY = "text[]"
    UUID = "uuid"


@dataclass
class _Property:
    name: str
    data_type: _DataType


class _CollectionConfig:
    def __init__(self, properties: list[_Property]) -> None:
        self.properties = properties
        self.reads = 0

    async def get(self) -> _CollectionConfig:
        self.reads += 1
        return self


class _Collection:
    def __init__(self, config: _CollectionConfig) -> None:
        self.config = config


class _Client:
    def __init__(self, configs: dict[str, _CollectionConfig]) -> None:
        self.collections = self
        self._configs = configs

    def get(self, name: str) -> _Collection:
        return _Collection(self._configs[name])


PROPERTIES = [
    _Property("title", _DataType.TEXT),
    _Property("views", _DataType.INT),
    _Property("published", _DataType.DATE),
    _Property("tags", _DataType.TEXT_ARRAY),
    _Property("ref", _DataType.UUID),
]


async def _store(
    allowlist: list[str], config: _CollectionConfig
) -> tuple[WeaviateVectorStore, DatasetMetadata]:
    cfg = {
        "http_url": "http://w.test:8080",
        "grpc_url": "http://w.test:50051",
        "api_key": "k",
        "collection_name": "C",
        "metadata_properties": allowlist,
    }
    store = WeaviateVectorStore(cfg)
    client = _Client({"C": config})

    async def connect():
        return client

    await client_cache.get_client(store.NAME, store.client_key(), connect)
    from syft_space.components.shared.metadata_types import MetadataFields

    return store, DatasetMetadata(MetadataFields(), WeaviateMetadataFields(cfg))


async def test_allowlisted_properties_are_typed_from_the_collection():
    store, metadata = await _store(
        ["title", "views", "published", "tags", "ref", "missing"],
        _CollectionConfig(PROPERTIES),
    )
    schema = await store.filter_schema(metadata)
    assert schema == {
        "title": FieldFilterSpec(
            type=MetadataType.STRING, ops=ops_for(MetadataType.STRING)
        ),
        "views": FieldFilterSpec(
            type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER)
        ),
        "published": FieldFilterSpec(
            type=MetadataType.DATETIME, ops=ops_for(MetadataType.DATETIME)
        ),
        "tags": FieldFilterSpec(
            type=MetadataType.STRING_LIST, ops=ops_for(MetadataType.STRING_LIST)
        ),
        "creation_time": FieldFilterSpec(
            type=MetadataType.DATETIME, ops=ops_for(MetadataType.DATETIME)
        ),
    }
    # ``ref`` (uuid) and ``missing`` (not in the collection) are not filterable
    assert FilterOperator.CONTAINS_ANY in schema["tags"].ops


async def test_without_an_allowlist_only_creation_time_is_filterable_and_no_read():
    config = _CollectionConfig(PROPERTIES)
    store, metadata = await _store([], config)
    schema = await store.filter_schema(metadata)
    assert set(schema) == {"creation_time"}
    assert config.reads == 0


async def test_the_collection_schema_is_read_once_per_client_and_dropped_on_evict():
    config = _CollectionConfig(PROPERTIES)
    store, metadata = await _store(["title"], config)
    await store.filter_schema(metadata)
    await store.filter_schema(metadata)
    assert config.reads == 1

    await client_cache.evict(store.NAME, store.client_key())
    client = _Client({"C": config})

    async def connect():
        return client

    await client_cache.get_client(store.NAME, store.client_key(), connect)
    await store.filter_schema(metadata)
    assert config.reads == 2


async def test_filter_schema_is_on_the_store_protocol():
    from syft_space.components.vector_stores.interfaces import BaseVectorStore

    assert hasattr(BaseVectorStore, "filter_schema")
    assert BaseVectorStore.FILTER_OPERATORS == frozenset()


@pytest.mark.parametrize("store_cls", [WeaviateVectorStore])
def test_remote_store_can_run_every_wire_operator(store_cls):
    from syft_space.components.shared.filter_types import WIRE_OPERATORS

    assert store_cls.FILTER_OPERATORS == WIRE_OPERATORS
