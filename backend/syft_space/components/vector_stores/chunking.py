"""Shared document chunking pipeline using Docling.

Parses an ``IngestFile`` into a sequence of text chunks plus
per-page images, then leaves storage and retrieval to whichever
``IngestableVectorStore`` invoked it.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from syft_space.components.shared.ingest_types import IngestFile

logger = logging.getLogger(__name__)

# Page images stored at ~/.syft-space/page_images/{collection_name}/{doc_id}/
PAGE_IMAGES_BASE_DIR = Path.home() / ".syft-space" / "page_images"

# API route prefix for serving document images
IMAGE_ENDPOINT_PREFIX = "/api/v1/datasets"

# Timeout per page for subprocess conversion (seconds).
# Total timeout = pages × this value.
_SUBPROCESS_TIMEOUT_PER_PAGE = 180


def _self_command() -> list[str]:
    """Return the command prefix to re-invoke this package's ``__main__``.

    Inside a PyInstaller frozen bundle ``sys.executable`` is the bundled
    exe itself, so we invoke it directly.  In development we need
    ``python -m syft_space`` to reach ``__main__.py``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "syft_space"]


def _extract_pictures_and_chunks(
    doc: Any,
    chunker: Any,
    images_dir: Path,
    doc_id: str,
    filename: str,
    file_size: int,
) -> list[dict[str, Any]]:
    """Extract pictures and chunk a docling Document.

    Shared by both the subprocess worker and the in-process path to
    avoid duplicating the picture-extraction + chunking logic.
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


def _worker_convert_pages() -> None:
    """Entry point for subprocess PDF page conversion.

    Called via ``__main__.py --convert-pdf-pages <args>``.
    Each subprocess loads docling fresh so the OS fully reclaims memory
    when the process exits, preventing C-level OOM on constrained systems.

    CLI args (via sys.argv[2:]):
        pdf_path, page_start, page_end, images_dir, doc_id,
        filename, file_size, result_path

    Writes a JSON object with keys ``chunks`` and ``failed_pages`` to
    *result_path*.  Using a file avoids stdout corruption from stray
    prints by docling / PIL / ONNX.
    """
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.base_models import (
        ConversionStatus,
        InputFormat,
    )
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.transforms.chunker import HybridChunker

    args = sys.argv[2:]
    pdf_path = Path(args[0])
    page_start = int(args[1])
    page_end = int(args[2])
    images_dir = Path(args[3])
    doc_id = args[4]
    filename = args[5]
    file_size = int(args[6])
    result_path = Path(args[7])

    # Force CPU: transformers' RT-DETRv2 (loaded by docling for layout
    # detection) creates float64 tensors directly on the configured device,
    # which MPS rejects. PYTORCH_ENABLE_MPS_FALLBACK doesn't catch direct
    # dtype creation, so the only reliable fix is to keep this off MPS.
    pipeline_options = PdfPipelineOptions(
        generate_picture_images=True,
        do_table_structure=True,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    page_nums = list(range(page_start, page_end + 1))
    chunks: list[dict[str, Any]] = []
    failed_pages: list[int] = []

    def _write_result() -> None:
        result_path.write_text(
            json.dumps({"chunks": chunks, "failed_pages": failed_pages})
        )

    try:
        result = converter.convert(
            pdf_path,
            page_range=(page_start, page_end),
            raises_on_error=False,
        )
    except (MemoryError, RuntimeError) as exc:
        print(
            f"Conversion crashed for pages {page_start}-{page_end}: {exc}",
            file=sys.stderr,
        )
        failed_pages = page_nums
        _write_result()
        return

    if result.status == ConversionStatus.FAILURE or result.document is None:
        print(
            f"Conversion failed for pages {page_start}-{page_end}",
            file=sys.stderr,
        )
        failed_pages = page_nums
        _write_result()
        return

    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        succeeded = {p.page_no for p in result.pages}
        failed_pages = [p for p in page_nums if p not in succeeded]

    doc = result.document
    chunker = HybridChunker()
    try:
        chunks = _extract_pictures_and_chunks(
            doc, chunker, images_dir, doc_id, filename, file_size
        )
    except Exception as exc:
        print(
            f"Extraction failed for pages {page_start}-{page_end}: {exc}",
            file=sys.stderr,
        )
        failed_pages = page_nums
    _write_result()


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


class DocumentChunker:
    """Shared Docling + HybridChunker pipeline for all dataset types.

    Handles document conversion, tokenizer-aware chunking, and image
    extraction. Converter and chunker are lazily initialized and shared
    across instances via class-level locks.

    Usage:
        chunker = DocumentChunker()
        chunks = chunker.parse_document(file)
        # Each chunk is a dict with: text, embedding_text, doc_id,
        # page_numbers, headings, picture_ids, file_name, file_type, file_size
    """

    _converter_lock = threading.Lock()
    _chunker_lock = threading.Lock()

    # Shared across all instances
    _converter = None
    _chunker = None

    @property
    def converter(self):
        """Lazily initialize Docling DocumentConverter.

        Used for non-PDF formats (DOCX, HTML, PPTX, etc.) which are
        converted in-process.  PDFs are always handled via subprocess
        isolation (see ``_convert_batched_pages``), where the worker
        creates its own converter with PDF-specific options.

        Thread-safe via double-checked locking.
        """
        from docling.document_converter import DocumentConverter

        if DocumentChunker._converter is None:
            with self._converter_lock:
                if DocumentChunker._converter is None:
                    DocumentChunker._converter = DocumentConverter()
        return DocumentChunker._converter

    @property
    def chunker(self):
        """Lazily initialize Docling HybridChunker.

        Uses the default tokenizer (all-MiniLM-L6-v2) to ensure chunk
        sizes align with the embedding model's context window.
        Thread-safe via double-checked locking.
        """
        from docling_core.transforms.chunker import HybridChunker

        if DocumentChunker._chunker is None:
            with self._chunker_lock:
                if DocumentChunker._chunker is None:
                    DocumentChunker._chunker = HybridChunker()
        return DocumentChunker._chunker

    @staticmethod
    def get_page_images_dir(collection_name: str, doc_id: str) -> Path:
        """Get the directory for storing page images for a document."""
        return PAGE_IMAGES_BASE_DIR / collection_name / doc_id

    @staticmethod
    def _get_pdf_page_count(pdf_path: Path) -> int:
        """Get total page count from a PDF file using pypdfium2."""
        import pypdfium2

        pdf_doc = pypdfium2.PdfDocument(pdf_path)
        try:
            return len(pdf_doc)
        finally:
            pdf_doc.close()

    def _extract_from_result(
        self,
        result: Any,
        images_dir: Path,
        doc_id: str,
        file: IngestFile,
    ) -> list[dict[str, Any]]:
        """Extract pictures and chunks from a single ConversionResult."""
        return _extract_pictures_and_chunks(
            result.document,
            self.chunker,
            images_dir,
            doc_id,
            file.filename,
            file.file_size or 0,
        )

    @staticmethod
    def _run_page_subprocess(
        pdf_path: Path,
        page_start: int,
        page_end: int,
        images_dir: Path,
        doc_id: str,
        file: IngestFile,
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Spawn a subprocess to convert a page range, returning (chunks, failed_pages).

        Each subprocess loads docling fresh and exits after conversion,
        ensuring the OS fully reclaims memory — prevents C-level OOM
        crashes that Python cannot catch.

        Results are exchanged via a temp JSON file (not stdout) so that
        stray prints from docling / PIL / ONNX cannot corrupt the data.
        """
        page_nums = list(range(page_start, page_end + 1))

        result_fd, result_path_str = tempfile.mkstemp(suffix=".json")
        result_path = Path(result_path_str)
        os.close(result_fd)
        try:
            cmd = [
                *_self_command(),
                "--convert-pdf-pages",
                str(pdf_path),
                str(page_start),
                str(page_end),
                str(images_dir),
                doc_id,
                file.filename,
                str(file.file_size or 0),
                str(result_path),
            ]
            num_pages = page_end - page_start + 1
            timeout = num_pages * _SUBPROCESS_TIMEOUT_PER_PAGE
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Subprocess timed out for pages %d-%d of %s",
                    page_start,
                    page_end,
                    file.filename,
                )
                return [], page_nums

            if proc.returncode != 0:
                logger.warning(
                    "Subprocess failed (rc=%d) for pages %d-%d of %s: %s",
                    proc.returncode,
                    page_start,
                    page_end,
                    file.filename,
                    proc.stderr[-500:] if proc.stderr else "(no stderr)",
                )
                # Worker may still have written a result file before crashing
                # — fall through to attempt reading it.

            try:
                data = json.loads(result_path.read_text())
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                logger.warning(
                    "No valid result file for pages %d-%d of %s: %s (stderr: %s)",
                    page_start,
                    page_end,
                    file.filename,
                    exc,
                    proc.stderr[-500:] if proc.stderr else "(no stderr)",
                )
                return [], page_nums

            chunks = data.get("chunks", [])
            failed_pages = data.get("failed_pages", [])
            # rc=0 doesn't imply success — the worker writes a valid result
            # file even when every page failed. Surface stderr in that case
            # so the cause isn't silently dropped.
            if not chunks and failed_pages and proc.stderr:
                logger.warning(
                    "Worker reported all pages failed for pages %d-%d of %s — stderr: %s",
                    page_start,
                    page_end,
                    file.filename,
                    proc.stderr[-1000:],
                )
            return chunks, failed_pages
        finally:
            result_path.unlink(missing_ok=True)

    def _convert_batched_pages(
        self,
        pdf_path: Path,
        file: IngestFile,
        total_pages: int,
        images_dir: Path,
        doc_id: str,
    ) -> list[dict[str, Any]]:
        """Convert specific PDF pages via subprocess isolation.

        First pass: sends all pages to a single subprocess, letting
        docling use its default internal batching (batch_size=4).
        Second pass: any pages that failed (OOM / segfault) are retried
        individually, each in its own fresh subprocess so the OS fully
        reclaims memory between pages.
        """
        page_start = 1
        page_end = total_pages

        # First pass — all pages in one subprocess
        logger.info(
            "Subprocess: converting pages %d-%d of %s",
            page_start,
            page_end,
            file.filename,
        )
        all_chunks, failed = self._run_page_subprocess(
            pdf_path, page_start, page_end, images_dir, doc_id, file
        )

        # Determine which pages still need retrying
        covered_pages: set[int] = set()
        for chunk in all_chunks:
            covered_pages.update(chunk["page_numbers"])
        retry_pages = [p for p in failed if p not in covered_pages]

        # Second pass — each failed page in its own subprocess
        if retry_pages:
            logger.info(
                "Retrying %d failed pages individually for %s: %s",
                len(retry_pages),
                file.filename,
                retry_pages,
            )
            for i, page_no in enumerate(retry_pages, 1):
                logger.info(
                    "Subprocess: page %d (%d/%d) of %s",
                    page_no,
                    i,
                    len(retry_pages),
                    file.filename,
                )
                chunks, _ = self._run_page_subprocess(
                    pdf_path, page_no, page_no, images_dir, doc_id, file
                )
                if chunks:
                    all_chunks.extend(chunks)
                else:
                    logger.warning(
                        "Page %d retry failed for %s, skipping",
                        page_no,
                        file.filename,
                    )

        return all_chunks

    def parse_document(
        self, file: IngestFile, collection_name: str
    ) -> list[dict[str, Any]]:
        """Parse document into chunks with metadata and save images to disk.

        Uses Docling for PDFs and other rich formats (DOCX, XLSX, HTML, etc.)
        with HybridChunker for tokenizer-aware chunking. Plain text/JSON files
        are handled directly without Docling overhead.

        PDFs are always processed via subprocess isolation to prevent
        C-level OOM (``std::bad_alloc``) from crashing the server.
        Subprocesses first attempt all pages in a single call; if that
        OOMs, failed pages are retried individually — each in a fresh
        process so the OS fully reclaims memory.

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

        # Simple text files - no Docling overhead needed
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

        # All other formats via Docling
        from docling.datamodel.base_models import DocumentStream
        from docling.exceptions import ConversionError

        images_dir = self.get_page_images_dir(collection_name, doc_id)

        # Non-PDF rich formats (DOCX, HTML, etc.) — single in-process convert
        if ext != ".pdf":
            source = DocumentStream(
                name=file.filename, stream=BytesIO(file.path.read_bytes())
            )
            result = self.converter.convert(source)
            return self._extract_from_result(result, images_dir, doc_id, file)

        # PDF path: always use subprocess isolation.  Docling's layout
        # model can trigger C-level std::bad_alloc that kills the process
        # outright — running in-process would crash the server.
        total_pages = self._get_pdf_page_count(file.path)
        if total_pages == 0:
            raise ConversionError(f"PDF has 0 pages: {file.filename}")

        chunks = self._convert_batched_pages(
            file.path, file, total_pages, images_dir, doc_id
        )

        # Sort by page number to preserve document order
        chunks.sort(key=lambda c: min(c["page_numbers"]) if c["page_numbers"] else 0)

        if not chunks:
            if images_dir.exists():
                shutil.rmtree(images_dir)
            raise ConversionError(f"All pages failed for {file.filename}")
        return chunks

    def purge_page_images(self, collection_name: str) -> None:
        """Purge all page images for a collection."""
        page_images_dir = PAGE_IMAGES_BASE_DIR / collection_name
        if page_images_dir.exists():
            shutil.rmtree(page_images_dir)
