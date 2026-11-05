"""Markdown front matter is metadata, not content.

The header is split off before conversion, so no chunk embeds it, and its
fields land on every chunk of the document as ``doc_*`` metadata.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from syft_space.components.chunking import chunker as chunker_module
from syft_space.components.chunking.chunker import DocumentChunker
from syft_space.components.chunking.front_matter import (
    MAX_HEADER_LINES,
    front_matter_metadata,
    split_front_matter,
)
from syft_space.components.shared.ingest_types import (
    IngestContext,
    IngestFile,
    IngestRequest,
)
from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as chroma_module,
)

BOM = chr(0xFEFF)

ARTICLE = (
    "---\n"
    'title: "Ramp Hits $60 Billion Valuation"\n'
    'source: "Bloomberg"\n'
    'author: "Rebecca Torrence"\n'
    'url: "https://www.bloomberg.com/news/articles/x"\n'
    'published_date: "2026-10-09T20:36:10Z"\n'
    'ingested_at: "2026-10-10T08:11:29Z"\n'
    'method: "extension"\n'
    "---\n"
    "\n"
    "# Ramp Hits $60 Billion Valuation\n"
    "\n"
    "Body text.\n"
)


# ============== split_front_matter ==============


def test_quoted_values_are_unquoted():
    fields, body = split_front_matter(ARTICLE)
    assert fields == {
        "title": "Ramp Hits $60 Billion Valuation",
        "source": "Bloomberg",
        "author": "Rebecca Torrence",
        "url": "https://www.bloomberg.com/news/articles/x",
        "published_date": "2026-10-09T20:36:10Z",
        "ingested_at": "2026-10-10T08:11:29Z",
        "method": "extension",
    }
    assert body == "\n# Ramp Hits $60 Billion Valuation\n\nBody text.\n"


def test_unquoted_values_and_dates_stay_as_written():
    text = "---\ntitle: Plain title\npublished_date: 2026-10-09T20:36:10Z\n---\nBody"
    fields, body = split_front_matter(text)
    assert fields == {
        "title": "Plain title",
        "published_date": "2026-10-09T20:36:10Z",
    }
    assert body == "Body"


def test_bom_is_skipped():
    fields, body = split_front_matter(BOM + "---\ntitle: T\n---\nBody\n")
    assert fields == {"title": "T"}
    assert body == "Body\n"


def test_crlf_line_endings():
    text = '---\r\ntitle: "T"\r\nauthor: A\r\n---\r\nBody\r\n'
    fields, body = split_front_matter(text)
    assert fields == {"title": "T", "author": "A"}
    assert body == "Body\r\n"


def test_body_starts_right_after_header():
    fields, body = split_front_matter("---\ntitle: T\n---\n# Heading\ntext")
    assert fields == {"title": "T"}
    assert body == "# Heading\ntext"


def test_header_only_file_has_empty_body():
    fields, body = split_front_matter("---\ntitle: T\n---")
    assert fields == {"title": "T"}
    assert body == ""


def test_other_flat_keys_are_kept():
    text = "---\nurl: https://x\ntype: article\nfeed_id: 42\nupdated-at: 2026\n---\nB"
    fields, _ = split_front_matter(text)
    assert fields == {
        "url": "https://x",
        "type": "article",
        "feed_id": 42,
        "updated-at": 2026,
    }


def test_no_header_is_unchanged():
    text = "# Title\n\ntitle: not a header\n"
    assert split_front_matter(text) == (None, text)


def test_unclosed_header_is_unchanged():
    text = "---\ntitle: T\n\n# Body without a closing delimiter\n"
    assert split_front_matter(text) == (None, text)


def test_horizontal_rule_later_in_text_is_not_a_header():
    text = "# Title\n\nIntro.\n\n---\n\ntitle: value\n\n---\n\nMore.\n"
    assert split_front_matter(text) == (None, text)


def test_horizontal_rule_after_header_stays_in_body():
    fields, body = split_front_matter("---\ntitle: T\n---\nA\n\n---\n\nB\n")
    assert fields == {"title": "T"}
    assert body == "A\n\n---\n\nB\n"


def test_opening_rule_and_prose_is_not_a_header():
    text = "---\n\nJust a paragraph after a rule.\n\n---\n\nMore.\n"
    assert split_front_matter(text) == (None, text)


def test_note_lines_without_known_key_are_not_a_header():
    text = "---\nNote: read this first\nWarning: draft\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_key_with_spaces_is_not_a_header():
    text = "---\ntitle: T\nPublished on: 2026-10-09\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_nested_lines_are_not_a_header():
    text = "---\ntitle: T\ntags:\n  - ml\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_delimiter_must_be_exact():
    text = "--- \ntitle: T\n---\nBody\n"
    assert split_front_matter(text) == (None, text)
    text = "---\ntitle: T\n----\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_empty_header_is_unchanged():
    text = "---\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_closing_beyond_line_limit_is_unchanged():
    lines = "".join(f"k{i}: v\n" for i in range(MAX_HEADER_LINES + 5))
    text = f"---\ntitle: T\n{lines}---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_closing_beyond_size_limit_is_unchanged():
    text = "---\ntitle: " + "x" * (70 * 1024) + "\n---\nBody\n"
    assert split_front_matter(text) == (None, text)


def test_flat_fallback_when_yaml_fails():
    # Unbalanced inner quotes are invalid YAML; the flat parser still reads it.
    text = '---\ntitle: "He said "hi" today"\nauthor: A\n---\nBody'
    fields, body = split_front_matter(text)
    assert fields == {"title": 'He said "hi" today', "author": "A"}
    assert body == "Body"


def test_yaml_flow_list_and_empty_value():
    text = "---\ntitle: T\ntags: [ml, nlp]\ncategory:\n---\nBody"
    fields, _ = split_front_matter(text)
    assert fields == {"title": "T", "tags": ["ml", "nlp"], "category": None}


# ============== front_matter_metadata ==============


def test_metadata_keys_are_prefixed_and_sanitised():
    out = front_matter_metadata(
        {"title": "T", "Published-Date": "2026", "feed id": 7, "Draft": True}
    )
    assert out == {
        "doc_title": "T",
        "doc_published_date": "2026",
        "doc_feed_id": 7,
        "doc_draft": True,
    }


def test_metadata_scalars_only():
    out = front_matter_metadata(
        {
            "tags": ["ml", "nlp", 3],
            "empty": [],
            "none": None,
            "nested": {"a": 1},
            "score": 1.5,
        }
    )
    assert out == {"doc_tags": "ml, nlp, 3", "doc_score": 1.5}


# ============== Ingestion ==============


class _BodyEchoBackend:
    """Returns one chunk per paragraph of whatever file it is handed."""

    def __init__(self):
        self.paths = []

    def convert_to_chunks(self, file, images_dir, doc_id, get_chunker):
        self.paths.append(file.path)
        text = file.path.read_text(encoding="utf-8")
        return [
            {
                "text": part.strip(),
                "embedding_text": part.strip(),
                "doc_id": doc_id,
                "page_numbers": [],
                "headings": [],
                "picture_ids": [],
                "file_name": file.filename,
                "file_type": ".md",
                "file_size": file.file_size or 0,
            }
            for part in text.split("\n\n")
            if part.strip()
        ]


class _FakeCollection:
    def __init__(self):
        self.documents: list[str] = []
        self.metadatas: list[dict[str, Any]] = []

    async def delete(self, where):
        pass

    async def add(self, ids, documents, embeddings, metadatas):
        self.documents.extend(documents)
        self.metadatas.extend(metadatas)


class _FakeClient:
    def __init__(self, collection):
        self._collection = collection

    async def get_or_create_collection(self, name, metadata):
        return self._collection


@pytest.fixture
def _backend(monkeypatch, tmp_path):
    backend = _BodyEchoBackend()
    monkeypatch.setattr(DocumentChunker, "_backend", backend)
    monkeypatch.setattr(chunker_module, "PAGE_IMAGES_BASE_DIR", tmp_path / "images")
    monkeypatch.setattr(chroma_module, "_chromadb_available", lambda: True)
    return backend


async def _ingest(path, metadata: dict[str, Any]) -> _FakeCollection:
    collection = _FakeCollection()
    store = chroma_module.ChromaDBLocalVectorStore.__new__(
        chroma_module.ChromaDBLocalVectorStore
    )
    store.config = SimpleNamespace(collection_name="col")
    store._document_chunker = DocumentChunker()
    store._generate_embeddings = lambda texts: [[0.0] for _ in texts]

    async def get_client():
        return _FakeClient(collection)

    store.get_client = get_client
    file = IngestFile(
        external_id=str(path),
        path=path,
        filename=path.name,
        file_size=path.stat().st_size,
        metadata=metadata,
    )
    ctx = IngestContext(
        sender="system@openmined.org",
        dataset_id="00000000-0000-0000-0000-000000000001",
    )
    await store.ingest(ctx, IngestRequest(files=[file]))
    return collection


async def test_ingested_chunks_carry_no_header_and_doc_metadata(tmp_path, _backend):
    source = tmp_path / "article.md"
    source.write_bytes(ARTICLE.encode("utf-8"))
    original = source.read_bytes()

    collection = await _ingest(source, {"source": "local_file", "file_name": "x"})

    assert collection.documents == [
        "# Ramp Hits $60 Billion Valuation",
        "Body text.",
    ]
    for meta in collection.metadatas:
        assert meta["doc_title"] == "Ramp Hits $60 Billion Valuation"
        assert meta["doc_source"] == "Bloomberg"
        assert meta["doc_author"] == "Rebecca Torrence"
        assert meta["doc_url"] == "https://www.bloomberg.com/news/articles/x"
        assert meta["doc_published_date"] == "2026-10-09T20:36:10Z"
        assert meta["doc_ingested_at"] == "2026-10-10T08:11:29Z"
        assert meta["doc_method"] == "extension"
        # Existing keys are untouched by the header.
        assert meta["source"] == "local_file"
        assert meta["file_name"] == "article.md"
    # The user's file is never rewritten; the body went through a temp file.
    assert source.read_bytes() == original
    assert _backend.paths[0] != source
    assert not _backend.paths[0].exists()


async def test_markdown_without_header_is_passed_through(tmp_path, _backend):
    source = tmp_path / "notes.md"
    source.write_bytes(b"---\nNote: text\n---\n\nkey: value\n")

    collection = await _ingest(source, {"source": "local_file"})

    assert _backend.paths == [source]
    assert "---\nNote: text\n---" in collection.documents
    for meta in collection.metadatas:
        assert [k for k in meta if k.startswith("doc_")] == ["doc_id"]


async def test_header_id_does_not_replace_doc_id(tmp_path, _backend):
    source = tmp_path / "a.md"
    source.write_bytes(b"---\ntitle: T\nid: header-id\n---\nBody\n")

    collection = await _ingest(source, {})

    assert collection.metadatas[0]["doc_id"] == chunker_module.derive_doc_id(
        str(source)
    )
