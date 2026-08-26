"""Source metadata must survive ingestion and be queryable.

Sources record what they know about an item — publication date, author,
link — in ``IngestFile.metadata``. That dict was passed to the chunker and
then dropped: the stored chunk metadata was built only from chunker output,
so every date and author was discarded at ingest.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from syft_space.components.shared.timestamps import parse_datetime
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    _chroma_scalars,
)


class TestParseDatetime:
    @pytest.mark.parametrize(
        ("label", "raw", "expected"),
        [
            (
                "RSS pubDate",
                "Tue, 25 Aug 2026 21:35:11 +0000",
                "2026-08-25T21:35:11+00:00",
            ),
            (
                "Atom offset",
                "2018-02-06T23:46:00.000-08:00",
                "2018-02-07T07:46:00+00:00",
            ),
            ("Blogger Z", "2024-03-01T00:00:00Z", "2024-03-01T00:00:00+00:00"),
            ("WP naive gmt", "2024-01-15T10:30:00", "2024-01-15T10:30:00+00:00"),
        ],
    )
    def test_real_source_formats(self, label, raw, expected):
        assert parse_datetime(raw).isoformat() == expected

    def test_naive_values_are_utc_not_local(self):
        # WordPress *_gmt fields carry no offset. Reading them as local time
        # shifts every date by the server's offset.
        assert parse_datetime("2024-01-15T10:30:00").tzinfo == timezone.utc

    @pytest.mark.parametrize("bad", ["", None, "not a date", "2024"])
    def test_unparseable_values_are_dropped_not_raised(self, bad):
        # A missing date is not worth failing an ingest over.
        assert parse_datetime(bad) is None


class TestChromaScalars:
    def test_datetime_yields_iso_and_epoch(self):
        # Metadata filtering compares numbers, so the epoch int is what makes
        # a date range queryable at all.
        out = _chroma_scalars({"published": datetime(2024, 3, 1, tzinfo=timezone.utc)})
        assert out["published"] == "2024-03-01T00:00:00+00:00"
        assert out["published_ts"] == 1709251200

    def test_naive_datetime_is_read_as_utc(self):
        out = _chroma_scalars({"published": datetime(2024, 1, 15, 10, 30)})
        assert out["published"] == "2024-01-15T10:30:00+00:00"
        assert out["published_ts"] == 1705314600

    def test_lists_are_joined(self):
        # ChromaDB rejects list values outright.
        assert _chroma_scalars({"labels": ["ml", "nlp"]})["labels"] == "ml,nlp"

    def test_none_is_dropped(self):
        assert "author" not in _chroma_scalars({"author": None})

    def test_scalars_pass_through(self):
        out = _chroma_scalars({"s": "x", "i": 1, "f": 1.5, "b": True})
        assert out == {"s": "x", "i": 1, "f": 1.5, "b": True}

    def test_unknown_types_are_stringified(self):
        assert _chroma_scalars({"o": {"a": 1}})["o"] == "{'a': 1}"

    def test_empty_metadata_is_empty(self):
        assert _chroma_scalars({}) == {}


class TestSourcesEmitDatetimes:
    """Sources hand over a datetime; the store decides how to serialize it."""

    async def test_blogspot_fetch_metadata_carries_datetimes(self, monkeypatch):
        import httpx

        from syft_space.components.sources.blogspot import blogspot_source as bs

        post = {
            "id": "10",
            "title": "Hello",
            "content": "<p>body</p>",
            "url": "https://example.blogspot.com/p/10",
            "updated": "2024-03-01T00:00:00Z",
            "published": "2018-02-06T23:46:00.000-08:00",
            "labels": ["ml"],
        }

        def handler(request):
            return httpx.Response(200, json=post, request=request)

        monkeypatch.setattr(
            bs,
            "_make_client",
            lambda: httpx.AsyncClient(
                base_url=bs.BLOGGER_API_ROOT, transport=httpx.MockTransport(handler)
            ),
        )
        source = bs.BlogspotSource(
            bs.BlogspotDatasetConfig.model_validate(
                {"blogUrls": "https://example.blogspot.com", "apiKey": "k"}
            )
        )
        async with source.fetch("1:10") as ingest_file:
            meta = ingest_file.metadata

        assert isinstance(meta["updated"], datetime)
        assert isinstance(meta["published"], datetime)
        # The fingerprint keeps the raw string it compares on.
        assert source.fingerprint("1:10") == "2024-03-01T00:00:00Z"

        stored = _chroma_scalars(meta)
        assert stored["published_ts"] == 1517989560
        assert stored["labels"] == "ml"


class TestStoredChunkMetadata:
    """The merge in ``_store_chunks``, without a live ChromaDB."""

    @staticmethod
    def _merge(source_metadata: dict) -> dict:
        """Mirror the dict build in _store_chunks for one chunk."""
        extra = _chroma_scalars(source_metadata)
        return {
            **extra,
            "doc_id": "abc123",
            "chunk_index": 0,
            "file_name": "post.html",
            "file_type": ".html",
        }

    def test_source_metadata_reaches_the_chunk(self):
        merged = self._merge(
            {
                "source": "wordpress",
                "link": "https://example.com/p/1",
                "modified_gmt": datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                "tags": [4, 7],
                "author": None,
            }
        )
        assert merged["source"] == "wordpress"
        assert merged["link"] == "https://example.com/p/1"
        assert merged["modified_gmt_ts"] == 1705314600
        assert merged["tags"] == "4,7"
        assert "author" not in merged

    def test_structural_keys_win_a_clash(self):
        # A source setting doc_id must not be able to break chunk identity.
        merged = self._merge({"doc_id": "hijacked", "file_name": "evil"})
        assert merged["doc_id"] == "abc123"
        assert merged["file_name"] == "post.html"
