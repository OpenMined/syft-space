"""Every source and store declares the metadata keys it emits, and the
dataset type composes those declarations into the public view.

The honesty tests run each contributor's real metadata-producing path and
assert that every key it writes is declared, hidden or not. A new key that
nobody declared fails here instead of reaching a hub user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from syft_space.components.dataset_types.interfaces import BaseDatasetType
from syft_space.components.shared.metadata_types import (
    DatasetMetadata,
    MetadataField,
    MetadataFields,
)
from syft_space.components.sources.blogspot import blogspot_source as bs
from syft_space.components.sources.local_file.local_file_source import (
    LocalFileMetadataFields,
    LocalFileProvider,
    LocalFileSource,
)
from syft_space.components.sources.noop_source import NoOpProvider
from syft_space.components.sources.rss.rss_source import (
    RssMetadataFields,
    RssProvider,
    _entry_metadata,
    _Feed,
)
from syft_space.components.sources.wordpress import wordpress_source as wp
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
    ChromaDBMetadataFields,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateMetadataFields,
    WeaviateVectorStore,
)


def _names(fields: tuple[MetadataField, ...]) -> set[str]:
    return {f.name for f in fields}


def _public(fields: tuple[MetadataField, ...]) -> set[str]:
    return {f.name for f in fields if not f.hidden}


def _public_of(meta: dict[str, Any], contributor: MetadataFields) -> dict[str, Any]:
    """Filter ``meta`` through one contributor's declaration alone."""
    return DatasetMetadata(contributor, MetadataFields()).public(meta)


# ============== injection ==============


@pytest.mark.parametrize(
    ("owner", "declaration"),
    [
        (RssProvider, RssMetadataFields),
        (wp.WordPressProvider, wp.WordPressMetadataFields),
        (bs.BlogspotProvider, bs.BlogspotMetadataFields),
        (LocalFileProvider, LocalFileMetadataFields),
        (NoOpProvider, MetadataFields),
        (ChromaDBLocalVectorStore, ChromaDBMetadataFields),
        (WeaviateVectorStore, WeaviateMetadataFields),
    ],
)
def test_every_contributor_injects_its_declaration(owner, declaration):
    assert owner.METADATA_FIELDS is declaration


# ============== sources: every emitted key is declared ==============


def test_rss_entry_metadata_is_fully_declared():
    feed = _Feed(url="https://example.com/feed", title="Example")
    entry = {
        "title": "Hello",
        "link": "https://example.com/p/1",
        "comments": "https://example.com/p/1#comments",
        "author": "Ada",
        "tags": [{"term": "ml"}],
        "published": "Mon, 01 Jan 2024 00:00:00 GMT",
    }
    emitted = set(_entry_metadata(feed, entry))
    assert emitted <= _names(RssMetadataFields().declared())


def test_wordpress_post_metadata_is_fully_declared():
    post = {
        "link": "https://example.com/hello",
        "date_gmt": "2024-01-10T09:00:00",
        "modified_gmt": "2024-01-15T10:30:00",
        "author": 1,
        "status": "publish",
        "_embedded": {"author": [{"name": "Ada"}], "wp:term": [[{"name": "T"}]]},
    }
    emitted = set(
        wp._post_metadata(
            post, post_type="post", post_id=7, title="Hello", slug="hello"
        )
    )
    assert emitted <= _names(wp.WordPressMetadataFields().declared())


def test_blogspot_post_metadata_is_fully_declared():
    post = {
        "url": "https://example.blogspot.com/p/10",
        "updated": "2024-03-01T00:00:00Z",
        "published": "2024-02-06T23:46:00.000-08:00",
        "labels": ["ml"],
        "author": {"displayName": "Ada"},
    }
    emitted = set(bs._post_metadata(post, blog_id="1", post_id="10", title="Hello"))
    assert emitted <= _names(bs.BlogspotMetadataFields().declared())


async def test_local_file_fetch_metadata_is_declared_and_hides_the_path(tmp_path):
    file = tmp_path / "doc.txt"
    file.write_text("x")
    source = LocalFileSource.__new__(LocalFileSource)
    async with source.fetch(str(file)) as ingest_file:
        meta = ingest_file.metadata
    fields = LocalFileMetadataFields()
    assert set(meta) <= _names(fields.declared())
    assert "absolute_path" not in _public_of(meta, fields)


# ============== ChromaDB: ingest-time and search-time keys ==============


class _Collection:
    def __init__(self) -> None:
        self.metadatas: list[dict[str, Any]] = []

    async def delete(self, where):
        return None

    async def add(self, ids, documents, embeddings, metadatas):
        self.metadatas.extend(metadatas)

    async def get(self, ids, include):
        return {"ids": list(ids), "documents": ["neighbour" for _ in ids]}


def _chroma() -> ChromaDBLocalVectorStore:
    store = ChromaDBLocalVectorStore.__new__(ChromaDBLocalVectorStore)
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]
    return store


def _chunk(i: int) -> dict[str, Any]:
    return {
        "doc_id": "abc",
        "embedding_text": f"e{i}",
        "text": f"t{i}",
        "file_name": "doc.html",
        "file_type": ".html",
        "file_size": 10,
        "page_numbers": [1],
        "headings": ["H"],
        "picture_ids": ["p.png"],
    }


def _chroma_metadata_for(source: MetadataFields) -> DatasetMetadata:
    return DatasetMetadata(source, ChromaDBMetadataFields())


async def test_chroma_ingest_time_keys_are_declared():
    # Mirrors ``ingest``: the source's dict plus the item's external_id.
    source_meta = {
        "source": "rss",
        "title": "Hello",
        "published": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "tags": ["a"],
        "external_id": "https://example.com/feed::guid",
    }
    collection = _Collection()
    await _chroma()._store_chunks(collection, [_chunk(0), _chunk(1)], source_meta)
    emitted = set().union(*(set(m) for m in collection.metadatas))
    assert emitted <= _names(_chroma_metadata_for(RssMetadataFields()).fields)


async def test_chroma_search_time_keys_are_declared():
    store = _chroma()
    results = {
        "ids": [["abc_1"]],
        "distances": [[0.1]],
        "documents": [["text"]],
        "metadatas": [
            [{"doc_id": "abc", "prev_chunk_id": "abc_0", "next_chunk_id": "abc_2"}]
        ],
    }
    docs, matched = store._process_query_results(results, "ds", 0.0, 5)
    await store._enrich_with_neighbor_context(_Collection(), docs, matched)
    emitted = set(docs[0].metadata)
    dm = _chroma_metadata_for(MetadataFields())
    assert emitted <= _names(dm.fields)
    assert set(dm.public(docs[0].metadata)) == {"doc_id", "image_urls"}


def test_chroma_derives_a_timestamp_twin_per_public_source_field():
    derived = _names(ChromaDBMetadataFields().derived(LocalFileMetadataFields()))
    assert derived == {"source_ts", "updated_ts"}  # not absolute_path_ts


# ============== Weaviate: declared from the owner's config ==============


def test_weaviate_declares_the_owner_allowlist_and_hides_its_internals():
    fields = WeaviateMetadataFields(
        {"metadata_properties": ["title", "author"], "content_property": "body"}
    )
    assert _public(fields.declared()) == {"title", "author", "creation_time"}
    meta = {
        "title": "t",
        "author": "a",
        "body": "…",
        "creation_time": "c",
        "distance": 0.2,
        "other": 1,
    }
    assert _public_of(meta, fields) == {
        "title": "t",
        "author": "a",
        "creation_time": "c",
    }


def test_weaviate_without_allowlist_declares_only_its_own_key():
    fields = WeaviateMetadataFields({"content_property": "body"})
    meta = {"title": "t", "body": "…", "distance": 0.2, "creation_time": "c"}
    assert _public_of(meta, fields) == {"creation_time": "c"}


# ============== dataset type: composition ==============


class _SrcFields(MetadataFields):
    fields = (MetadataField(name="title"), MetadataField(name="secret", hidden=True))


class _StoreFields(MetadataFields):
    fields = (MetadataField(name="doc_id"), MetadataField(name="prev", hidden=True))

    def derived(self, source):
        return tuple(
            MetadataField(name=f"{f.name}_ts")
            for f in source.declared()
            if not f.hidden
        )


class _Provider:
    NAME = "fake"
    METADATA_FIELDS = _SrcFields

    @classmethod
    def for_ingest(cls, cfg):
        return object()


class _Store:
    NAME = "fake_store"
    METADATA_FIELDS = _StoreFields

    def __init__(self, cfg):
        pass


class _Binding(BaseDatasetType):
    NAME = "fake_binding"
    SOURCE_PROVIDER_CLS = _Provider
    VECTOR_STORE_CLS = _Store

    @classmethod
    def split_config(cls, configuration):
        return {}, {}


def test_binding_composes_both_declarations_once():
    binding = _Binding({})
    assert isinstance(binding.metadata, DatasetMetadata)
    assert _names(binding.metadata.fields) == {
        "title",
        "secret",
        "doc_id",
        "prev",
        "title_ts",
    }
    meta = {
        "title": "t",
        "secret": "s",
        "doc_id": "d",
        "prev": "p",
        "title_ts": 1,
        "unknown": "u",
    }
    assert binding.public_metadata(meta) == {"title": "t", "doc_id": "d", "title_ts": 1}
