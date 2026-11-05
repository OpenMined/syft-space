"""Preparing chunks: what makes a fit basis for a question and what does not."""

from datetime import UTC, datetime
from typing import Any

from syft_benchmark.sources import is_useful, load_documents, strip_header
from syft_benchmark.sources.chroma import Chunk, _added_at, _doc_meta


def test_header_is_separated_from_body() -> None:
    """The ETL puts its header at the start of the first chunk.

    As a source of questions it is useless, as a source of metadata quite the
    opposite, so it is cut off rather than thrown away.
    """
    raw = (
        "---\n"
        'title: "The SyftHub architecture"\n'
        'source: "docs"\n'
        'url: "https://example.org/a"\n'
        "\n"
        "The hub stores endpoint descriptions, but not the data itself."
    )
    body, header = strip_header(raw)

    assert header["title"] == "The SyftHub architecture"
    assert header["url"] == "https://example.org/a"
    assert body == "The hub stores endpoint descriptions, but not the data itself."


def test_collector_header_is_separated_whole() -> None:
    """The news collector adds `type` and `feed_id` after the common keys."""
    raw = (
        "---\n"
        'title: "A story"\n'
        'published_date: "2026-10-05T18:14:35Z"\n'
        'method: "playwright"\n'
        'type: "article"\n'
        'feed_id: "Article/17933"\n'
        "---\n"
        "\n"
        "# A story\n"
        "\n"
        "Body text."
    )
    body, header = strip_header(raw)

    assert header["feed_id"] == "Article/17933"
    assert body == "# A story\n\nBody text."


def test_unknown_keys_stay_in_the_body() -> None:
    """Ordinary text with a colon is not a header."""
    body, header = strip_header("Conclusion: the hub does not store documents.")
    assert header == {}
    assert body.startswith("Conclusion:")


def test_short_chunk_is_not_useful() -> None:
    assert not is_useful("Far too short.", min_chars=400)


def test_ordinary_text_passes() -> None:
    text = (
        "The hub stores endpoint descriptions and metadata about them, but not "
        "the documents themselves. "
    ) * 4 + "You can subscribe to updates in your profile settings."
    assert is_useful(text, min_chars=400)


def test_consent_banner_is_rejected() -> None:
    """Counting goes by all occurrences, not by the number of distinct markers.

    A consent banner repeats "cookie" a dozen times, whereas an ordinary
    paragraph mentions a subscription once and stays in work.
    """
    banner = (
        "We use cookie technology. Functional cookie files and analytics "
        "cookie files require your consent. See our privacy policy. "
    ) * 4
    assert not is_useful(banner, min_chars=100)


# --- assembling documents: the header from metadata or from chunk 0 ----------

_BODY = "Source: Reuters reported on Monday that the hub stores no documents."


class _Client:
    """A collection whose chunks carry the given raw Chroma metadata."""

    def __init__(self, rows: list[tuple[str, int, str, dict[str, Any]]]) -> None:
        self.rows = rows

    def iter_chunks(self, collection_id: str) -> Any:
        for doc_id, index, text, meta in self.rows:
            yield Chunk(
                chunk_id=f"{doc_id}_{index}",
                doc_id=doc_id,
                chunk_index=index,
                text=text,
                file_name=f"{doc_id}.md",
                headings="",
                published=str(meta.get("published") or ""),
                added_at=_added_at(meta),
                doc_meta=_doc_meta(meta),
            )


def _load(rows: list[tuple[str, int, str, dict[str, Any]]]) -> dict[str, Any]:
    docs = load_documents(_Client(rows), "c", min_chars=0)  # type: ignore[arg-type]
    return {d.doc_id: d for d in docs}


_LIFTED = {
    "doc_id": "new",
    "source": "local_file",
    "file_name": "new.md",
    "doc_title": "Lifted title",
    "doc_source": "Reuters",
    "doc_url": "https://example.org/new",
    "doc_published_date": "2026-10-05",
    "doc_ingested_at": "2026-10-06T08:00:00Z",
    "doc_tags": "a, b",
}


def test_doc_meta_skips_the_space_keys() -> None:
    assert _doc_meta(_LIFTED) == {
        "title": "Lifted title",
        "source": "Reuters",
        "url": "https://example.org/new",
        "published_date": "2026-10-05",
        "ingested_at": "2026-10-06T08:00:00Z",
        "tags": "a, b",
    }


def test_header_is_read_from_the_chunk_metadata() -> None:
    doc = _load(
        [
            ("new", 0, "First body paragraph.", _LIFTED),
            ("new", 1, "Second body paragraph.", _LIFTED),
        ]
    )["new"]

    assert doc.title == "Lifted title"
    assert doc.url == "https://example.org/new"
    assert doc.source == "Reuters"
    assert doc.published_at == datetime(2026, 10, 5, tzinfo=UTC)
    assert doc.published_whole_day is True
    assert doc.ingested_at == datetime(2026, 10, 6, 8, tzinfo=UTC)
    assert [c.text for c in doc.chunks] == [
        "First body paragraph.",
        "Second body paragraph.",
    ]


def test_header_in_chunk_zero_is_still_read() -> None:
    """Collections indexed before the Space lifted the header into metadata."""
    text = (
        "---\n"
        'title: "Old title"\n'
        'url: "https://example.org/old"\n'
        'published_date: "2026-10-04"\n'
        "---\n"
        "Old body."
    )
    doc = _load([("old", 0, text, {"source": "local_file"})])["old"]

    assert doc.title == "Old title"
    assert doc.url == "https://example.org/old"
    assert doc.published_at == datetime(2026, 10, 4, tzinfo=UTC)
    assert doc.chunks[0].text == "Old body."


def test_metadata_wins_over_a_header_in_the_text() -> None:
    text = 'title: "Text title"\npublished_date: "2020-01-01"\n---\nBody.'
    doc = _load([("new", 0, text, _LIFTED)])["new"]

    assert doc.title == "Lifted title"
    assert doc.published_at == datetime(2026, 10, 5, tzinfo=UTC)


def test_body_is_not_stripped_when_metadata_carries_the_header() -> None:
    """With the header in metadata, chunk 0 is body even if it looks like one."""
    doc = _load([("new", 0, _BODY, _LIFTED)])["new"]

    assert doc.chunks[0].text == _BODY
    assert doc.source == "Reuters"
