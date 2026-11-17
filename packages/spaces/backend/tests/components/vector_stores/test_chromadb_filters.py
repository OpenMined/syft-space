"""ChromaDB: the validated tree as a ``where`` clause, list metadata written
as arrays, the clause reaching ``collection.query``, and the one-off rewrite
of older comma-joined chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from syft_space.components.shared.filter_types import (
    FieldFilterSpec,
    FilterNode,
    FilterValidationError,
    ops_for,
    validate_filters,
)
from syft_space.components.shared.metadata_types import (
    DatasetMetadata,
    MetadataField,
    MetadataFields,
    MetadataType,
)
from syft_space.components.shared.search_types import SearchContext, SearchParameters
from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as store_module,
)
from syft_space.components.vector_stores.chromadb_local import list_migration
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
    ChromaDBMetadataFields,
)
from syft_space.components.vector_stores.chromadb_local.filters import build_where
from syft_space.components.vector_stores.chromadb_local.list_migration import (
    MIGRATED_FLAG,
    migrate_collection,
    migrate_datasets,
    split_legacy_lists,
)

NODE = TypeAdapter(FilterNode)

SPEC = {
    "title": FieldFilterSpec(
        type=MetadataType.STRING, ops=ops_for(MetadataType.STRING)
    ),
    "price": FieldFilterSpec(
        type=MetadataType.NUMBER, ops=ops_for(MetadataType.NUMBER)
    ),
    "published": FieldFilterSpec(
        type=MetadataType.DATETIME, ops=ops_for(MetadataType.DATETIME)
    ),
    "tags": FieldFilterSpec(
        type=MetadataType.STRING_LIST, ops=ops_for(MetadataType.STRING_LIST)
    ),
}


def _cond(field: str, op: str, value) -> dict:
    return {"type": "condition", "field": field, "op": op, "value": value}


def _where(node: dict) -> dict[str, Any]:
    return build_where(validate_filters(NODE.validate_python(node), SPEC))


# ============== translation ==============


@pytest.mark.parametrize(
    ("op", "chroma_op"),
    [
        ("eq", "$eq"),
        ("ne", "$ne"),
        ("gt", "$gt"),
        ("gte", "$gte"),
        ("lt", "$lt"),
        ("lte", "$lte"),
    ],
)
def test_comparisons_map_one_to_one(op, chroma_op):
    assert _where(_cond("price", op, "3")) == {"price": {chroma_op: 3}}


def test_in_and_nin_take_the_list():
    assert _where(_cond("price", "in", [1, 2])) == {"price": {"$in": [1, 2]}}
    assert _where(_cond("title", "nin", ["a"])) == {"title": {"$nin": ["a"]}}


def test_a_datetime_targets_the_epoch_twin():
    assert _where(_cond("published", "gte", "2024-01-01")) == {
        "published_ts": {
            "$gte": int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
        }
    }


def test_contains_any_is_an_or_of_contains_and_contains_all_an_and():
    assert _where(_cond("tags", "contains_any", ["a", "b"])) == {
        "$or": [{"tags": {"$contains": "a"}}, {"tags": {"$contains": "b"}}]
    }
    assert _where(_cond("tags", "contains_all", ["a", "b"])) == {
        "$and": [{"tags": {"$contains": "a"}}, {"tags": {"$contains": "b"}}]
    }


def test_single_operands_are_unwrapped_because_chroma_wants_two():
    assert _where(_cond("tags", "contains_any", ["a"])) == {"tags": {"$contains": "a"}}
    assert _where(
        {"type": "group", "op": "and", "operands": [_cond("price", "eq", 1)]}
    ) == {"price": {"$eq": 1}}


def test_groups_nest_as_and_or():
    where = _where(
        {
            "type": "group",
            "op": "and",
            "operands": [
                _cond("price", "gt", 1),
                {
                    "type": "group",
                    "op": "or",
                    "operands": [_cond("title", "eq", "a"), _cond("title", "eq", "b")],
                },
            ],
        }
    )
    assert where == {
        "$and": [
            {"price": {"$gt": 1}},
            {"$or": [{"title": {"$eq": "a"}}, {"title": {"$eq": "b"}}]},
        ]
    }


def test_not_never_reaches_the_translator():
    with pytest.raises(FilterValidationError):
        _where({"type": "group", "op": "not", "operands": [_cond("price", "eq", 1)]})


# ============== the clause reaches the query; lists are written as arrays ==============


class _Collection:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}
        self.metadatas: list[dict[str, Any]] = []

    async def query(self, **kwargs):
        self.query_kwargs = kwargs
        return {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]}

    async def delete(self, where):
        return None

    async def add(self, ids, documents, embeddings, metadatas):
        self.metadatas.extend(metadatas)


def _store() -> ChromaDBLocalVectorStore:
    store = ChromaDBLocalVectorStore.__new__(ChromaDBLocalVectorStore)
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]
    return store


async def test_search_passes_the_where_clause(monkeypatch):
    monkeypatch.setattr(store_module, "_chromadb_available", lambda: True)
    store = _store()
    collection = _Collection()

    class _Client:
        async def get_collection(self, name):
            return collection

    async def get_client():
        return _Client()

    store.get_client = get_client  # type: ignore[method-assign]
    store.config = type("C", (), {"collection_name": "c"})()
    filters = validate_filters(NODE.validate_python(_cond("price", "lt", 5)), SPEC)
    ctx = SearchContext(sender="u@example.org", dataset_id=uuid4())
    await store.search(ctx, "q", SearchParameters(filters=filters))
    assert collection.query_kwargs["where"] == {"price": {"$lt": 5}}

    await store.search(ctx, "q", SearchParameters())
    assert collection.query_kwargs["where"] is None


async def test_chunk_list_keys_are_arrays_and_empty_ones_are_absent():
    collection = _Collection()
    chunks = [
        {
            "doc_id": "d",
            "embedding_text": "e",
            "text": "t",
            "file_name": "f.pdf",
            "file_type": ".pdf",
            "file_size": 1,
            "page_numbers": [4, 7],
            "headings": ["A", "B > C"],
            "picture_ids": [],
        }
    ]
    await _store()._store_chunks(collection, chunks, {"tags": ["x"]})
    meta = collection.metadatas[0]
    assert meta["page_numbers"] == [4, 7]
    assert meta["headings"] == ["A", "B > C"]
    assert meta["tags"] == ["x"]
    assert "picture_ids" not in meta


def test_image_urls_accept_a_list_and_a_legacy_joined_string():
    from syft_space.components.chunking.chunker import build_image_urls

    assert build_image_urls("ds", "doc", ["a.png", "b.png"]) == build_image_urls(
        "ds", "doc", "a.png,b.png"
    )
    assert build_image_urls("ds", "doc", []) == []


# ============== rewrite of older chunks ==============

LIST_FIELDS = {
    "tags": MetadataType.STRING_LIST,
    "headings": MetadataType.STRING_LIST,
    "page_numbers": MetadataType.NUMBER_LIST,
}


def test_split_joins_by_the_separator_each_key_used():
    delta = split_legacy_lists(
        {
            "tags": "a,b",
            "headings": "Intro > Setup",
            "page_numbers": "1,2",
            "title": "t",
        },
        LIST_FIELDS,
    )
    assert delta == {
        "tags": ["a", "b"],
        "headings": ["Intro", "Setup"],
        "page_numbers": [1, 2],
    }


def test_split_drops_an_empty_string_and_leaves_arrays_and_unparsable_numbers():
    delta = split_legacy_lists(
        {"tags": "", "headings": ["done"], "page_numbers": "one,two"}, LIST_FIELDS
    )
    assert delta == {"tags": None}


class _LegacyCollection:
    name = "Collection_c"

    def __init__(self, rows: dict[str, dict[str, Any]], metadata=None) -> None:
        self.rows = rows
        self.metadata = metadata
        self.updates: list[tuple[list[str], list[dict]]] = []

    async def get(self, limit, offset, include):
        ids = list(self.rows)[offset : offset + limit]
        return {"ids": ids, "metadatas": [self.rows[i] for i in ids]}

    async def update(self, ids, metadatas):
        self.updates.append((ids, metadatas))
        for id, delta in zip(ids, metadatas, strict=True):
            for k, v in delta.items():
                if v is None:
                    self.rows[id].pop(k, None)
                else:
                    self.rows[id][k] = v

    async def modify(self, metadata):
        self.metadata = metadata


async def test_migration_rewrites_only_changed_keys_of_changed_chunks_and_flags_the_collection(
    monkeypatch,
):
    monkeypatch.setattr(list_migration, "_BATCH", 2)
    collection = _LegacyCollection(
        {
            "1": {"tags": "a,b", "title": "t"},
            "2": {"tags": ["new"], "title": "t"},
            "3": {"tags": "", "page_numbers": "3"},
        }
    )
    changed = await migrate_collection(collection, LIST_FIELDS)
    assert changed == 2
    assert collection.updates == [
        (["1"], [{"tags": ["a", "b"]}]),
        (["3"], [{"tags": None, "page_numbers": [3]}]),
    ]
    assert collection.rows["3"] == {"page_numbers": [3]}
    assert collection.metadata == {MIGRATED_FLAG: True}


async def test_the_flag_write_leaves_hnsw_keys_out_but_keeps_the_rest():
    collection = _LegacyCollection(
        {"1": {"tags": "a"}}, metadata={"hnsw:space": "cosine", "owner": "me"}
    )
    await migrate_collection(collection, LIST_FIELDS)
    assert collection.metadata == {"owner": "me", MIGRATED_FLAG: True}


async def test_a_flagged_collection_is_not_read_again():
    collection = _LegacyCollection(
        {"1": {"tags": "a,b"}}, metadata={MIGRATED_FLAG: True}
    )
    assert await migrate_collection(collection, LIST_FIELDS) == 0
    assert collection.updates == []


async def test_the_store_migrates_every_declared_list_field_including_hidden(
    monkeypatch,
):
    monkeypatch.setattr(store_module, "_chromadb_available", lambda: True)
    seen: dict[str, Any] = {}

    async def fake_migrate(collection, list_fields):
        seen["fields"] = list_fields
        return 1

    monkeypatch.setattr(store_module, "migrate_collection", fake_migrate)
    store = _store()

    class _Client:
        async def get_collection(self, name):
            return object()

    async def get_client():
        return _Client()

    store.get_client = get_client  # type: ignore[method-assign]
    store.config = type("C", (), {"collection_name": "c"})()

    class _Source(MetadataFields):
        fields = (MetadataField(name="tags", type=MetadataType.STRING_LIST),)

    metadata = DatasetMetadata(_Source(), ChromaDBMetadataFields())
    assert await store.migrate_list_fields(metadata) == 1
    assert seen["fields"] == {
        "tags": MetadataType.STRING_LIST,
        "page_numbers": MetadataType.NUMBER_LIST,
        "headings": MetadataType.STRING_LIST,
        "image_urls": MetadataType.STRING_LIST,
        "picture_ids": MetadataType.STRING_LIST,
    }


async def test_migrate_datasets_builds_only_the_store_and_survives_a_failure(
    monkeypatch,
):
    calls: list[str] = []

    class _Store:
        def __init__(self, cfg) -> None:
            self.cfg = cfg

        async def migrate_list_fields(self, metadata):
            calls.append(self.cfg["name"])
            if self.cfg["name"] == "bad":
                raise RuntimeError("down")
            return 0

    class _Binding:
        VECTOR_STORE_CLS = _Store

        @classmethod
        def split_config(cls, configuration):
            return {}, configuration

        @classmethod
        def metadata_for(cls, configuration):
            return None

    class _NoMigration:
        VECTOR_STORE_CLS = object

    registry = {"chroma": _Binding, "remote": _NoMigration}
    datasets = [
        type(
            "D", (), {"dtype": "chroma", "configuration": {"name": "bad"}, "name": "b"}
        )(),
        type("D", (), {"dtype": "remote", "configuration": {}, "name": "r"})(),
        type("D", (), {"dtype": "gone", "configuration": {}, "name": "g"})(),
        type(
            "D", (), {"dtype": "chroma", "configuration": {"name": "ok"}, "name": "o"}
        )(),
    ]
    await migrate_datasets(datasets, registry.__getitem__)
    assert calls == ["bad", "ok"]
