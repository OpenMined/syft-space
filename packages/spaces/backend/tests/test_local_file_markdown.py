"""``LocalFileSource.fetch`` on Markdown files with a front matter header.

The header is split off before the chunker sees the file: its fields travel
as ``doc_*`` metadata, and the body goes to a temp file headed by the title.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from syft_space.components.chunking import chunker as chunker_module
from syft_space.components.chunking.chunker import DocumentChunker
from syft_space.components.shared.ingest_types import (
    IngestContext,
    IngestFile,
    IngestRequest,
)
from syft_space.components.sources.local_file.local_file_source import (
    LocalFileSource,
)
from syft_space.components.vector_stores.chromadb_local import (
    chromadb_vector_store as chroma_module,
)

ARTICLE = (
    "---\n"
    'title: "Ramp Hits $60 Billion Valuation"\n'
    'source: "Bloomberg"\n'
    'author: "Rebecca Torrence"\n'
    'url: "https://www.bloomberg.com/news/articles/x"\n'
    'published_date: "2026-10-09T20:36:10Z"\n'
    'updated: "2020-01-01"\n'
    "---\n"
    "\n"
    "Body text.\n"
)


def _source() -> LocalFileSource:
    return LocalFileSource.__new__(LocalFileSource)


# ============== fetch ==============


async def test_header_is_split_into_doc_metadata(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(ARTICLE.encode("utf-8"))

    async with _source().fetch(str(path)) as file:
        meta = file.metadata
        body = file.path.read_text(encoding="utf-8")

    assert meta["doc_title"] == "Ramp Hits $60 Billion Valuation"
    assert meta["doc_source"] == "Bloomberg"
    assert meta["doc_author"] == "Rebecca Torrence"
    assert meta["doc_url"] == "https://www.bloomberg.com/news/articles/x"
    assert meta["doc_published_date"] == "2026-10-09T20:36:10Z"
    assert meta["title"] == "Ramp Hits $60 Billion Valuation"
    assert meta["author"] == "Rebecca Torrence"
    assert meta["url"] == "https://www.bloomberg.com/news/articles/x"
    assert meta["published"].isoformat() == "2026-10-09T20:36:10+00:00"
    assert body == "# Ramp Hits $60 Billion Valuation\n\nBody text.\n"
    assert file.filename == "article.md"
    assert file.external_id == str(path)
    assert file.file_size == path.stat().st_size


async def test_source_keys_win_over_header_keys(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(ARTICLE.encode("utf-8"))

    async with _source().fetch(str(path)) as file:
        meta = file.metadata

    assert meta["source"] == "local_file"
    assert meta["doc_source"] == "Bloomberg"
    assert meta["updated"].year != 2020
    assert meta["doc_updated"] == "2020-01-01"
    assert meta["absolute_path"] == str(path)


async def test_temp_file_is_removed_and_original_untouched(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(ARTICLE.encode("utf-8"))

    async with _source().fetch(str(path)) as file:
        tmp = file.path
        assert tmp != path
        assert tmp.exists()

    assert not tmp.exists()
    assert path.read_bytes() == ARTICLE.encode("utf-8")


async def test_temp_file_is_removed_when_the_body_raises(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(ARTICLE.encode("utf-8"))

    with pytest.raises(RuntimeError):
        async with _source().fetch(str(path)) as file:
            tmp = file.path
            raise RuntimeError("ingest failed")

    assert not tmp.exists()


async def test_existing_title_heading_is_not_doubled(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(b"---\ntitle: T\n---\n\n# T\n\nBody\n")

    async with _source().fetch(str(path)) as file:
        body = file.path.read_text(encoding="utf-8")

    assert body == "\n# T\n\nBody\n"


async def test_header_without_title_keeps_body_as_is(tmp_path):
    path = tmp_path / "article.md"
    path.write_bytes(b"---\nauthor: A\n---\nBody\n")

    async with _source().fetch(str(path)) as file:
        body = file.path.read_text(encoding="utf-8")
        meta = file.metadata

    assert body == "Body\n"
    assert meta["doc_author"] == "A"


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes.md", b"---\nNote: text\n---\n\nkey: value\n"),
        ("plain.md", b"# Title\n\nBody\n"),
        ("latin1.md", "---\ntitle: café\n---\nBody\n".encode("latin-1")),
        ("article.txt", ARTICLE.encode("utf-8")),
    ],
)
async def test_files_without_a_header_are_passed_through(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)

    async with _source().fetch(str(path)) as file:
        assert file.path == path
        meta = file.metadata

    assert not [k for k in meta if k.startswith("doc_")]
    assert path.read_bytes() == content


async def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        async with _source().fetch(str(tmp_path / "gone.md")):
            pass


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


async def _ingest(file: IngestFile) -> _FakeCollection:
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
    ctx = IngestContext(
        sender="system@openmined.org",
        dataset_id="00000000-0000-0000-0000-000000000001",
    )
    await store.ingest(ctx, IngestRequest(files=[file]))
    return collection


async def test_ingested_chunks_carry_title_and_doc_metadata(tmp_path, _backend):
    path = tmp_path / "article.md"
    path.write_bytes(ARTICLE.encode("utf-8"))

    async with _source().fetch(str(path)) as file:
        collection = await _ingest(file)

    assert collection.documents == [
        "# Ramp Hits $60 Billion Valuation",
        "Body text.",
    ]
    for meta in collection.metadatas:
        assert meta["doc_title"] == "Ramp Hits $60 Billion Valuation"
        assert meta["doc_source"] == "Bloomberg"
        assert meta["source"] == "local_file"
        assert meta["file_name"] == "article.md"
        assert meta["external_id"] == str(path)


async def test_header_id_does_not_replace_doc_id(tmp_path, _backend):
    path = tmp_path / "a.md"
    path.write_bytes(b"---\ntitle: T\nid: header-id\n---\nBody\n")

    async with _source().fetch(str(path)) as file:
        collection = await _ingest(file)

    assert collection.metadatas[0]["doc_id"] == chunker_module.derive_doc_id(str(path))


async def test_chunker_converts_markdown_as_given(tmp_path, _backend):
    path = tmp_path / "a.md"
    path.write_bytes(ARTICLE.encode("utf-8"))
    file = IngestFile(
        external_id=str(path),
        path=path,
        filename=path.name,
        file_size=path.stat().st_size,
        metadata={},
    )

    collection = await _ingest(file)

    assert _backend.paths == [path]
    assert collection.documents[0].startswith("---\ntitle:")
