"""In-process docling conversion backend.

Non-PDF rich formats convert in-process. PDFs always run in isolated
subprocesses (``_worker_convert_pages``) so a C-level OOM in docling's
layout stack cannot crash the server; failed pages are retried
individually in fresh processes.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

from loguru import logger

from syft_space.components.chunking.chunker import (
    _build_hybrid_chunker,
    _extract_pictures_and_chunks,
    _get_pdf_page_count,
)
from syft_space.components.shared.cancellation import CancelToken
from syft_space.components.shared.ingest_types import IngestCancelled, IngestFile

# Timeout per page for subprocess conversion (seconds).
# Total timeout = pages × this value.
_SUBPROCESS_TIMEOUT_PER_PAGE = 180

# Most pages one subprocess converts. Memory grows with the batch, while
# each batch costs only one model load (a few seconds).
BATCH_PAGES = 25


def _format_duration(seconds: float) -> str:
    """Seconds as ``42s``, ``3m05s`` or ``1h02m``."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m{total % 60:02d}s"
    return f"{total // 3600}h{total % 3600 // 60:02d}m"


def _self_command() -> list[str]:
    """Return the command prefix to re-invoke this package's ``__main__``.

    Inside a PyInstaller frozen bundle ``sys.executable`` is the bundled
    exe itself, so we invoke it directly.  In development we need
    ``python -m syft_space`` to reach ``__main__.py``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "syft_space"]


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
    chunker = _build_hybrid_chunker(heuristic=False)
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


class LocalDoclingBackend:
    """Converts documents with the docling library in this process.

    The DocumentConverter is lazily initialized and shared across
    instances via a class-level lock.
    """

    _converter_lock = threading.Lock()

    # Shared across all instances
    _converter = None

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

        if LocalDoclingBackend._converter is None:
            with self._converter_lock:
                if LocalDoclingBackend._converter is None:
                    LocalDoclingBackend._converter = DocumentConverter()
        return LocalDoclingBackend._converter

    def convert_to_chunks(
        self,
        file: IngestFile,
        images_dir: Path,
        doc_id: str,
        get_chunker: Callable[[], Any],
        cancel: CancelToken | None = None,
    ) -> list[dict[str, Any]]:
        """Convert ``file`` into chunk dicts, saving pictures to ``images_dir``.

        PDFs are always processed via subprocess isolation to prevent
        C-level OOM (``std::bad_alloc``) from crashing the server. They are
        converted in batches of ``BATCH_PAGES`` pages; a batch that fails is
        halved and retried until the failing pages are isolated.

        Setting ``cancel`` kills the running PDF subprocess and raises
        ``IngestCancelled``.
        """
        from docling.datamodel.base_models import DocumentStream
        from docling.exceptions import ConversionError

        cancel = cancel or CancelToken()

        ext = Path(file.filename).suffix.lower()

        # Non-PDF rich formats (DOCX, HTML, etc.) — single in-process convert.
        if ext != ".pdf":
            source = DocumentStream(
                name=file.filename, stream=BytesIO(file.path.read_bytes())
            )
            result = self.converter.convert(source)
            return _extract_pictures_and_chunks(
                result.document,
                get_chunker(),
                images_dir,
                doc_id,
                file.filename,
                file.file_size or 0,
            )

        # PDF path: always use subprocess isolation.  The worker builds
        # its own converter and chunker, so ``get_chunker`` is not used.
        total_pages = _get_pdf_page_count(file.path)
        if total_pages == 0:
            raise ConversionError(f"PDF has 0 pages: {file.filename}")

        chunks = self._convert_batched_pages(
            file.path, file, total_pages, images_dir, doc_id, cancel
        )

        # Sort by page number to preserve document order
        chunks.sort(key=lambda c: min(c["page_numbers"]) if c["page_numbers"] else 0)

        if not chunks:
            if images_dir.exists():
                shutil.rmtree(images_dir)
            raise ConversionError(f"All pages failed for {file.filename}")
        return chunks

    @staticmethod
    def _run_page_subprocess(
        pdf_path: Path,
        page_start: int,
        page_end: int,
        images_dir: Path,
        doc_id: str,
        file: IngestFile,
        cancel: CancelToken,
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Spawn a subprocess to convert a page range, returning (chunks, failed_pages).

        Raises ``IngestCancelled`` if ``cancel`` is set before or during the run.

        Each subprocess loads docling fresh and exits after conversion,
        ensuring the OS fully reclaims memory — prevents C-level OOM
        crashes that Python cannot catch.

        Results are exchanged via a temp JSON file (not stdout) so that
        stray prints from docling / PIL / ONNX cannot corrupt the data.
        """
        if cancel.cancelled:
            raise IngestCancelled(f"Cancelled while converting {file.filename}")
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
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                # Cancelling kills the subprocess, which ends the wait below.
                with cancel.on_cancel(proc.kill):
                    _, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                logger.warning(
                    "Subprocess timed out for pages {}-{} of {}",
                    page_start,
                    page_end,
                    file.filename,
                )
                return [], page_nums

            if cancel.cancelled:
                raise IngestCancelled(f"Cancelled while converting {file.filename}")

            if proc.returncode != 0:
                logger.warning(
                    "Subprocess failed (rc={}) for pages {}-{} of {}: {}",
                    proc.returncode,
                    page_start,
                    page_end,
                    file.filename,
                    stderr[-500:] if stderr else "(no stderr)",
                )
                # Worker may still have written a result file before crashing
                # — fall through to attempt reading it.

            try:
                data = json.loads(result_path.read_text())
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                logger.warning(
                    "No valid result file for pages {}-{} of {}: {} (stderr: {})",
                    page_start,
                    page_end,
                    file.filename,
                    exc,
                    stderr[-500:] if stderr else "(no stderr)",
                )
                return [], page_nums

            chunks = data.get("chunks", [])
            failed_pages = data.get("failed_pages", [])
            # rc=0 doesn't imply success — the worker writes a valid result
            # file even when every page failed. Surface stderr in that case
            # so the cause isn't silently dropped.
            if not chunks and failed_pages and stderr:
                logger.warning(
                    "Worker reported all pages failed for pages {}-{} of {} — stderr: {}",
                    page_start,
                    page_end,
                    file.filename,
                    stderr[-1000:],
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
        cancel: CancelToken,
    ) -> list[dict[str, Any]]:
        """Convert a PDF in batches of at most ``BATCH_PAGES`` pages.

        Each batch runs in its own subprocess, so memory use does not grow
        with the length of the document. A batch that fails is narrowed
        down by ``_convert_range``. Logs one progress line per batch.
        """
        all_chunks: list[dict[str, Any]] = []
        skipped: list[int] = []
        started = time.monotonic()
        for page_start in range(1, total_pages + 1, BATCH_PAGES):
            page_end = min(page_start + BATCH_PAGES - 1, total_pages)
            chunks, failed = self._convert_range(
                pdf_path, page_start, page_end, images_dir, doc_id, file, cancel
            )
            all_chunks.extend(chunks)
            skipped.extend(failed)

            elapsed = time.monotonic() - started
            if page_end < total_pages:
                remaining = elapsed / page_end * (total_pages - page_end)
                logger.info(
                    "Converting {}: {}/{} pages ({}%), {} elapsed, about {} left",
                    file.filename,
                    page_end,
                    total_pages,
                    page_end * 100 // total_pages,
                    _format_duration(elapsed),
                    _format_duration(remaining),
                )

        logger.info(
            "Converted {}: {} pages in {}, {} skipped",
            file.filename,
            total_pages,
            _format_duration(time.monotonic() - started),
            len(skipped),
        )
        return all_chunks

    def _convert_range(
        self,
        pdf_path: Path,
        page_start: int,
        page_end: int,
        images_dir: Path,
        doc_id: str,
        file: IngestFile,
        cancel: CancelToken,
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Convert pages ``page_start``..``page_end``, narrowing down failures.

        - Every page failed (the subprocess was killed or crashed): halve the
          range and convert each half, down to single pages.
        - Some pages failed: keep what converted and retry those pages alone.
        - A single page that fails is skipped.

        Returns the chunks and the pages that were skipped.
        """
        logger.debug(
            "Subprocess: converting pages {}-{} of {}",
            page_start,
            page_end,
            file.filename,
        )
        chunks, failed = self._run_page_subprocess(
            pdf_path, page_start, page_end, images_dir, doc_id, file, cancel
        )

        # A page counts as failed only if no chunk came back for it.
        covered_pages: set[int] = set()
        for chunk in chunks:
            covered_pages.update(chunk["page_numbers"])
        failed = [p for p in failed if p not in covered_pages]
        if not failed:
            return chunks, []

        if page_start == page_end:
            logger.warning(
                "Page {} of {} failed on its own, skipping", page_start, file.filename
            )
            return chunks, [page_start]

        if len(failed) == page_end - page_start + 1:
            middle = (page_start + page_end) // 2
            halves = ((page_start, middle), (middle + 1, page_end))
        else:
            halves = tuple((p, p) for p in failed)

        skipped: list[int] = []
        for start, end in halves:
            more_chunks, more_skipped = self._convert_range(
                pdf_path, start, end, images_dir, doc_id, file, cancel
            )
            chunks.extend(more_chunks)
            skipped.extend(more_skipped)
        return chunks, skipped
