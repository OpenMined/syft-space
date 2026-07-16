"""Shared document chunking pipeline using Docling.

Parses an ``IngestFile`` into a sequence of text chunks plus
per-page images, then leaves storage and retrieval to whichever
``IngestableVectorStore`` invoked it.

Conversion runs through a pluggable backend: in-process docling by
default (``docling_local``), or a docling-serve instance when
``SYFT_DOCLING_SERVE_URL`` is set (``docling_remote``). Both backends
funnel into the same extraction + chunking helpers here, so they
produce identical chunks.
"""

import logging
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.config import app_settings

logger = logging.getLogger(__name__)

# Page images stored at ~/.syft-space/page_images/{collection_name}/{doc_id}/
PAGE_IMAGES_BASE_DIR = Path.home() / ".syft-space" / "page_images"

# API route prefix for serving document images
IMAGE_ENDPOINT_PREFIX = "/api/v1/datasets"

# Tabular sources docling models as one giant table item. They use the fast
# heuristic tokenizer (which never wedges); everything else uses the accurate
# HF tokenizer. See _build_hybrid_chunker.
_TABULAR_EXTS = {".csv", ".xls", ".xlsx"}


def _heuristic_count_tokens(text: str) -> int:
    """Approximate token count (~4 chars/token) — no model, no network.

    Good enough to size chunks to the embedder's window; the ONNX embedder
    does the real, truncating embedding downstream. Defined at module scope so
    it is a stable, hashable callable (docling's prose splitter memoises on it).
    """
    return max(1, len(text) // 4)


def _extract_pictures_and_chunks(
    doc: Any,
    chunker: Any,
    images_dir: Path,
    doc_id: str,
    filename: str,
    file_size: int,
) -> list[dict[str, Any]]:
    """Extract pictures and chunk a docling Document.

    Shared by every conversion path — the in-process converter, the PDF
    subprocess worker, and the remote docling-serve backend — to
    guarantee they all produce identical chunk dicts.
    """
    picture_page_map: dict[int, list[str]] = {}
    images_dir_created = False
    for picture in doc.pictures:
        pil_image = picture.get_image(doc)
        if pil_image:
            if not images_dir_created:
                images_dir.mkdir(parents=True, exist_ok=True)
                images_dir_created = True
            pic_filename = f"{uuid4().hex}.png"
            pil_image.save(images_dir / pic_filename, "PNG")
            if picture.prov:
                for prov in picture.prov:
                    picture_page_map.setdefault(prov.page_no, []).append(pic_filename)

    chunks: list[dict[str, Any]] = []
    for chunk in chunker.chunk(doc):
        page_numbers = sorted(
            {
                prov.page_no
                for item in chunk.meta.doc_items
                for prov in (item.prov or [])
            }
        )
        chunk_picture_ids: list[str] = []
        for pn in page_numbers:
            chunk_picture_ids.extend(picture_page_map.get(pn, []))
        chunk_picture_ids = sorted(set(chunk_picture_ids))

        chunks.append(
            {
                "text": chunk.text,
                "embedding_text": chunker.contextualize(chunk),
                "doc_id": doc_id,
                "page_numbers": page_numbers,
                "headings": chunk.meta.headings or [],
                "picture_ids": chunk_picture_ids,
                "file_name": filename,
                "file_type": Path(filename).suffix.lower(),
                "file_size": file_size,
            }
        )
    return chunks


def _build_hybrid_chunker(heuristic: bool):
    """Build a HybridChunker with either the accurate or the heuristic tokenizer.

    Two tokenizers, picked by content kind:

    - ``heuristic=False`` (prose: PDF/DOCX/HTML/...) — the default
      ``all-MiniLM-L6-v2`` tokenizer from the HF Hub. Accurate token sizing, so
      no chunk gets silently truncated at embed time. Wedge-safe here because
      only a single multi-megabyte *table* item is pathologically slow to
      tokenise, and prose documents don't contain one.

    - ``heuristic=True`` (tabular: CSV/XLSX) — a dependency-free ~4-chars/token
      counter. Docling models a whole sheet as one giant table item; tokenising
      its serialisation with a real tokenizer wedges (600s+), so the heuristic
      keeps it fast. Tabular text runs well above 4 chars/token, so the count
      over-estimates and never under-splits into truncated chunks.

    (Embeddings run on ChromaDB's local ONNX model, so they never touch HF.)
    """
    from docling_core.transforms.chunker import HybridChunker

    if not heuristic:
        return HybridChunker()

    from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer

    class _HeuristicTokenizer(BaseTokenizer):
        max_tokens: int = 256

        def count_tokens(self, text: str) -> int:
            return _heuristic_count_tokens(text)

        def get_max_tokens(self) -> int:
            return self.max_tokens

        def get_tokenizer(self):
            # Docling's prose splitter (semchunk) calls this and uses the
            # result as a token-counter callable, so return the counter itself.
            return _heuristic_count_tokens

    return HybridChunker(tokenizer=_HeuristicTokenizer())


def _get_pdf_page_count(pdf_path: Path) -> int:
    """Get total page count from a PDF file using pypdfium2."""
    import pypdfium2

    pdf_doc = pypdfium2.PdfDocument(pdf_path)
    try:
        return len(pdf_doc)
    finally:
        pdf_doc.close()


def build_image_urls(dataset_id: str, doc_id: str, picture_ids: str) -> list[str]:
    """Build image endpoint URLs from chunk metadata.

    Uses dataset_id (not collection_name) in URLs to avoid leaking
    internal collection names in public-facing responses.

    Args:
        dataset_id: Dataset identifier (public-facing key)
        doc_id: Hash-based document identifier
        picture_ids: Comma-separated picture filenames (e.g. "ab12cd34ef56.png,...")

    Returns:
        List of URI paths like
        ["/api/v1/datasets/{dataset_id}/images/{doc_id}/{uuid_hex}.png", ...]
    """
    urls: list[str] = []
    if not doc_id or not dataset_id:
        return urls
    for pic in picture_ids.split(","):
        if pic.strip():
            urls.append(
                f"{IMAGE_ENDPOINT_PREFIX}/{dataset_id}/images/{doc_id}/{pic.strip()}"
            )
    return urls


class DoclingBackend(Protocol):
    """Strategy that converts one document into chunk dicts.

    Implementations own the conversion transport (in-process docling,
    docling-serve, ...) but must write picture PNGs to ``images_dir``
    and return the chunk dict shape documented on
    ``DocumentChunker.parse_document``.
    """

    def convert_to_chunks(
        self,
        file: IngestFile,
        images_dir: Path,
        doc_id: str,
        get_chunker: Callable[[], Any],
    ) -> list[dict[str, Any]]:
        """Convert ``file`` into chunk dicts, saving pictures to ``images_dir``.

        ``get_chunker`` lazily returns the HybridChunker appropriate for
        the file's content kind (backends that chunk elsewhere — e.g. the
        PDF subprocess worker — may never call it).
        """
        ...


def _resolve_backend() -> DoclingBackend:
    """Pick the conversion backend from ``SYFT_DOCLING_SERVE_URL``.

    Unset: documents are converted in-process with the docling library
    (PDFs in isolated subprocesses). Set: conversion is delegated to
    that docling-serve instance; extraction and chunking still run
    locally.
    """
    if app_settings.docling_serve_url:
        from syft_space.components.vector_stores.docling_remote import (
            RemoteDoclingBackend,
        )
        from syft_space.components.vector_stores.docling_serve_client import (
            DoclingServeClient,
        )

        return RemoteDoclingBackend(
            DoclingServeClient(str(app_settings.docling_serve_url))
        )

    from syft_space.components.vector_stores.docling_local import LocalDoclingBackend

    return LocalDoclingBackend()


class DocumentChunker:
    """Shared docling conversion + HybridChunker pipeline for all dataset types.

    Handles document conversion (through the resolved ``DoclingBackend``),
    tokenizer-aware chunking, and image extraction. Backend and chunkers
    are lazily initialized and shared across instances via class-level
    locks.

    Usage:
        chunker = DocumentChunker()
        chunks = chunker.parse_document(file)
        # Each chunk is a dict with: text, embedding_text, doc_id,
        # page_numbers, headings, picture_ids, file_name, file_type, file_size
    """

    _backend_lock = threading.Lock()
    _chunker_lock = threading.Lock()

    # Shared across all instances
    _backend: DoclingBackend | None = None
    # Two chunkers: the accurate HF tokenizer for prose, the fast heuristic for
    # tabular sources (see _build_hybrid_chunker). Lazily built and cached.
    _chunker_prose = None
    _chunker_tabular = None

    def _get_backend(self) -> DoclingBackend:
        """Lazily resolve+cache the conversion backend (see _resolve_backend).

        Thread-safe via double-checked locking.
        """
        if DocumentChunker._backend is None:
            with self._backend_lock:
                if DocumentChunker._backend is None:
                    DocumentChunker._backend = _resolve_backend()
        return DocumentChunker._backend

    def _get_chunker(self, tabular: bool):
        """Lazily build+cache the HybridChunker for this content kind.

        ``tabular`` selects the fast heuristic tokenizer (CSV/XLSX); otherwise
        the accurate HF tokenizer (prose). Thread-safe via double-checked
        locking.
        """
        if tabular:
            if DocumentChunker._chunker_tabular is None:
                with self._chunker_lock:
                    if DocumentChunker._chunker_tabular is None:
                        DocumentChunker._chunker_tabular = _build_hybrid_chunker(
                            heuristic=True
                        )
            return DocumentChunker._chunker_tabular

        if DocumentChunker._chunker_prose is None:
            with self._chunker_lock:
                if DocumentChunker._chunker_prose is None:
                    DocumentChunker._chunker_prose = _build_hybrid_chunker(
                        heuristic=False
                    )
        return DocumentChunker._chunker_prose

    @staticmethod
    def get_page_images_dir(collection_name: str, doc_id: str) -> Path:
        """Get the directory for storing page images for a document."""
        return PAGE_IMAGES_BASE_DIR / collection_name / doc_id

    def parse_document(
        self, file: IngestFile, collection_name: str
    ) -> list[dict[str, Any]]:
        """Parse document into chunks with metadata and save images to disk.

        Uses docling for PDFs and other rich formats (DOCX, XLSX, HTML,
        etc.) with HybridChunker for tokenizer-aware chunking — via the
        in-process backend or a remote docling-serve instance, depending
        on ``SYFT_DOCLING_SERVE_URL``. Plain text/JSON files are handled
        directly without docling overhead.

        Args:
            file: IngestFile to parse
            collection_name: Dataset collection name (used for image storage partitioning)

        Returns:
            List of chunk dicts, each with keys:
                text: clean text for storage/display
                embedding_text: heading-enriched text for embedding
                doc_id: unique document identifier (UUID-based)
                page_numbers: list[int] of referenced pages
                headings: list[str] of section headings
                picture_ids: list[str] of extracted picture filenames
                file_name: original filename
                file_type: MIME type
                file_size: size in bytes
        """
        ext = Path(file.filename).suffix.lower()
        doc_id = uuid4().hex[:16]

        # Simple text files - no docling overhead needed
        if ext in [".json", ".txt"]:
            content = file.path.read_text(encoding="utf-8")
            return [
                {
                    "text": content,
                    "embedding_text": content,
                    "doc_id": doc_id,
                    "page_numbers": [],
                    "headings": [],
                    "picture_ids": [],
                    "file_name": file.filename,
                    "file_type": ext,
                    "file_size": file.file_size or 0,
                }
            ]

        images_dir = self.get_page_images_dir(collection_name, doc_id)

        def get_chunker():
            return self._get_chunker(tabular=ext in _TABULAR_EXTS)

        return self._get_backend().convert_to_chunks(
            file, images_dir, doc_id, get_chunker
        )

    def purge_page_images(self, collection_name: str) -> None:
        """Purge all page images for a collection."""
        page_images_dir = PAGE_IMAGES_BASE_DIR / collection_name
        if page_images_dir.exists():
            shutil.rmtree(page_images_dir)
