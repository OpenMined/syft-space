"""Docling conversion backends (``SYFT_DOCLING_SERVE_URL``): backend
resolution, the docling-serve client, and the remote backend."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.vector_stores import docling_remote
from syft_space.components.vector_stores.chunking import (
    DocumentChunker,
    _build_hybrid_chunker,
    _resolve_backend,
)
from syft_space.components.vector_stores.docling_local import LocalDoclingBackend
from syft_space.components.vector_stores.docling_remote import RemoteDoclingBackend
from syft_space.components.vector_stores.docling_serve_client import (
    DoclingServeClient,
    DoclingServeError,
)
from syft_space.config import app_settings

# ============== Backend resolution ==============


def test_default_resolves_local_backend():
    assert app_settings.docling_serve_url is None
    assert isinstance(_resolve_backend(), LocalDoclingBackend)


def test_url_resolves_remote_backend(monkeypatch):
    monkeypatch.setattr(app_settings, "docling_serve_url", "http://docling:5001")
    backend = _resolve_backend()
    assert isinstance(backend, RemoteDoclingBackend)
    assert backend._client.base_url == "http://docling:5001"


# ============== docling-serve client ==============

# The client passes json_content through untouched, so client tests
# need no real DoclingDocument (and no docling install).
_RAW_DOC = {"schema_name": "DoclingDocument", "name": "test"}


def _doc_dict(text: str = "Hello from docling-serve.") -> dict[str, Any]:
    """Real DoclingDocument dict — for tests that deserialize it."""
    docling_core = pytest.importorskip("docling_core")  # noqa: F841
    from docling_core.types.doc.document import DoclingDocument
    from docling_core.types.doc.labels import DocItemLabel

    doc = DoclingDocument(name="test")
    if text:
        doc.add_text(label=DocItemLabel.TEXT, text=text)
    return doc.export_to_dict()


class _FakeServer:
    """Scripted docling-serve served through httpx.MockTransport."""

    def __init__(
        self,
        poll_statuses: list[str],
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ):
        self.poll_statuses = list(poll_statuses)
        self.result = result
        self.error_message = error_message
        self.submit_requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/convert/file/async":
            self.submit_requests.append(request)
            return httpx.Response(200, json={"task_id": "t1", "task_status": "pending"})
        if request.url.path == "/v1/status/poll/t1":
            status = self.poll_statuses.pop(0)
            return httpx.Response(
                200,
                json={
                    "task_id": "t1",
                    "task_status": status,
                    "error_message": self.error_message,
                },
            )
        if request.url.path == "/v1/result/t1":
            return httpx.Response(200, json=self.result)
        raise AssertionError(f"unexpected path {request.url.path}")


def _make_client(server: _FakeServer) -> DoclingServeClient:
    client = DoclingServeClient("http://docling:5001", poll_interval_seconds=0.0)
    client._build_http_client = lambda: httpx.Client(  # type: ignore[method-assign]
        base_url=client.base_url, transport=httpx.MockTransport(server.handler)
    )
    return client


def test_client_happy_path_returns_json_content(tmp_path):
    server = _FakeServer(
        poll_statuses=["pending", "started", "success"],
        result={
            "document": {"json_content": _RAW_DOC},
            "status": "success",
            "errors": [],
        },
    )
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    got = _make_client(server).convert_to_docling_dict(source, "a.docx", 60.0)

    assert got == _RAW_DOC


def test_client_pins_conversion_options(tmp_path):
    server = _FakeServer(
        poll_statuses=["success"],
        result={"document": {"json_content": _RAW_DOC}, "status": "success"},
    )
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    _make_client(server).convert_to_docling_dict(source, "a.docx", 60.0)

    body = server.submit_requests[0].read()
    for field, value in {
        "to_formats": b"json",
        "image_export_mode": b"embedded",
        "images_scale": b"1.0",
    }.items():
        assert field.encode() in body and value in body


def test_client_task_failure_raises(tmp_path):
    server = _FakeServer(poll_statuses=["failure"], error_message="boom")
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    with pytest.raises(DoclingServeError, match="boom"):
        _make_client(server).convert_to_docling_dict(source, "a.docx", 60.0)


def test_client_failed_result_status_raises(tmp_path):
    server = _FakeServer(
        poll_statuses=["skipped"],
        result={"document": {"json_content": None}, "status": "skipped"},
    )
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    with pytest.raises(DoclingServeError, match="status=skipped"):
        _make_client(server).convert_to_docling_dict(source, "a.docx", 60.0)


def test_client_unreachable_raises(tmp_path):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = DoclingServeClient("http://docling:5001")
    client._build_http_client = lambda: httpx.Client(  # type: ignore[method-assign]
        base_url=client.base_url, transport=httpx.MockTransport(refuse)
    )
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    with pytest.raises(DoclingServeError, match="unavailable"):
        client.convert_to_docling_dict(source, "a.docx", 60.0)


def test_client_times_out_when_task_never_finishes(tmp_path):
    server = _FakeServer(poll_statuses=["pending", "pending", "pending"])
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")

    with pytest.raises(TimeoutError):
        _make_client(server).convert_to_docling_dict(source, "a.docx", 0.0)


# ============== Remote backend ==============


class _FakeConvertClient:
    """Stands in for DoclingServeClient in RemoteDoclingBackend tests."""

    def __init__(self, json_content: dict[str, Any]):
        self.json_content = json_content
        self.calls: list[dict[str, Any]] = []

    def convert_to_docling_dict(self, path, filename, timeout_seconds):
        self.calls.append({"filename": filename, "timeout_seconds": timeout_seconds})
        return self.json_content


def _heuristic_chunker():
    return _build_hybrid_chunker(heuristic=True)


def test_remote_backend_produces_chunks(tmp_path):
    fake = _FakeConvertClient(_doc_dict("Remote conversion works."))
    backend = RemoteDoclingBackend(fake)  # type: ignore[arg-type]
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")
    file = IngestFile(path=source, filename="a.docx", file_size=4)

    chunks = backend.convert_to_chunks(
        file, tmp_path / "images", "doc1", _heuristic_chunker
    )

    assert len(chunks) == 1
    assert chunks[0]["text"] == "Remote conversion works."
    assert chunks[0]["doc_id"] == "doc1"
    assert chunks[0]["file_name"] == "a.docx"
    assert fake.calls[0]["timeout_seconds"] == docling_remote._DEFAULT_TIMEOUT


def test_remote_backend_pdf_timeout_scales_with_pages(tmp_path, monkeypatch):
    fake = _FakeConvertClient(_doc_dict("Some pdf text."))
    backend = RemoteDoclingBackend(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(docling_remote, "_get_pdf_page_count", lambda _: 5)
    source = tmp_path / "a.pdf"
    source.write_bytes(b"fake")
    file = IngestFile(path=source, filename="a.pdf", file_size=4)

    backend.convert_to_chunks(file, tmp_path / "images", "doc1", _heuristic_chunker)

    assert fake.calls[0]["timeout_seconds"] == 5 * docling_remote._PDF_TIMEOUT_PER_PAGE


def test_remote_backend_empty_pdf_result_raises(tmp_path, monkeypatch):
    pytest.importorskip("docling")
    from docling.exceptions import ConversionError

    fake = _FakeConvertClient(_doc_dict(text=""))
    backend = RemoteDoclingBackend(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(docling_remote, "_get_pdf_page_count", lambda _: 1)
    source = tmp_path / "a.pdf"
    source.write_bytes(b"fake")
    file = IngestFile(path=source, filename="a.pdf", file_size=4)

    with pytest.raises(ConversionError, match="All pages failed"):
        backend.convert_to_chunks(file, tmp_path / "images", "doc1", _heuristic_chunker)


# ============== Facade delegation ==============


@pytest.fixture
def _reset_backend():
    original = DocumentChunker._backend
    yield
    DocumentChunker._backend = original


class _RecordingBackend:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def convert_to_chunks(self, file, images_dir, doc_id, get_chunker):
        self.calls.append({"file": file, "images_dir": images_dir, "doc_id": doc_id})
        return []


def test_facade_txt_shortcut_bypasses_backend(tmp_path, _reset_backend):
    class _Exploding:
        def convert_to_chunks(self, *args, **kwargs):
            raise AssertionError("backend must not run for .txt")

    DocumentChunker._backend = _Exploding()
    source = tmp_path / "notes.txt"
    source.write_text("plain text")
    file = IngestFile(path=source, filename="notes.txt", file_size=10)

    chunks = DocumentChunker().parse_document(file, "col")

    assert len(chunks) == 1
    assert chunks[0]["text"] == "plain text"


def test_facade_delegates_docling_formats_to_backend(tmp_path, _reset_backend):
    backend = _RecordingBackend()
    DocumentChunker._backend = backend
    source = tmp_path / "a.docx"
    source.write_bytes(b"fake")
    file = IngestFile(path=source, filename="a.docx", file_size=4)

    DocumentChunker().parse_document(file, "col")

    call = backend.calls[0]
    assert call["file"] is file
    assert call["images_dir"] == DocumentChunker.get_page_images_dir(
        "col", call["doc_id"]
    )
    assert len(call["doc_id"]) == 16
