"""Remote docling conversion backend (docling-serve).

Only conversion runs remotely: docling-serve returns the lossless
DoclingDocument, then picture extraction and chunking run locally
through the same helpers as the in-process backend, so both backends
produce identical chunks. PDFs need no subprocess isolation here —
conversion memory pressure lives in the docling-serve container.
"""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from syft_space.components.shared.ingest_types import IngestFile
from syft_space.components.vector_stores.chunking import (
    _extract_pictures_and_chunks,
    _get_pdf_page_count,
)
from syft_space.components.vector_stores.docling_serve_client import DoclingServeClient

logger = logging.getLogger(__name__)

# Conversion deadlines: PDFs scale with page count (mirroring the local
# subprocess budget); everything else gets a flat allowance.
_PDF_TIMEOUT_PER_PAGE = 180
_DEFAULT_TIMEOUT = 1800


class RemoteDoclingBackend:
    """Converts documents through a docling-serve instance."""

    def __init__(self, client: DoclingServeClient):
        self._client = client

    def convert_to_chunks(
        self,
        file: IngestFile,
        images_dir: Path,
        doc_id: str,
        get_chunker: Callable[[], Any],
    ) -> list[dict[str, Any]]:
        """Convert ``file`` into chunk dicts, saving pictures to ``images_dir``."""
        from docling.exceptions import ConversionError
        from docling_core.types.doc.document import DoclingDocument

        ext = Path(file.filename).suffix.lower()

        timeout = _DEFAULT_TIMEOUT
        if ext == ".pdf":
            total_pages = _get_pdf_page_count(file.path)
            if total_pages == 0:
                raise ConversionError(f"PDF has 0 pages: {file.filename}")
            timeout = total_pages * _PDF_TIMEOUT_PER_PAGE

        json_content = self._client.convert_to_docling_dict(
            file.path, file.filename, timeout_seconds=timeout
        )
        doc = DoclingDocument.model_validate(json_content)

        chunks = _extract_pictures_and_chunks(
            doc, get_chunker(), images_dir, doc_id, file.filename, file.file_size or 0
        )

        # Pictures without image bytes are the fingerprint of a server
        # that ignored image_export_mode=embedded — warn instead of
        # silently ingesting an image-less document.
        if doc.pictures and not images_dir.exists():
            logger.warning(
                "docling-serve returned %d pictures without image data for %s "
                "— no images extracted",
                len(doc.pictures),
                file.filename,
            )

        # Sort by page number to preserve document order (stable, so
        # documents without page provenance keep their original order).
        chunks.sort(key=lambda c: min(c["page_numbers"]) if c["page_numbers"] else 0)

        if ext == ".pdf" and not chunks:
            if images_dir.exists():
                shutil.rmtree(images_dir)
            raise ConversionError(f"All pages failed for {file.filename}")
        return chunks
