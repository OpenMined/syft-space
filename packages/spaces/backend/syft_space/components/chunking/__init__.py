"""Document chunking component.

Sits between sources and vector stores in the ingestion pipeline:
converts an ``IngestFile`` into text chunks + page images, via
in-process docling or a remote docling-serve instance
(``SYFT_DOCLING_SERVE_URL``).
"""

from syft_space.components.chunking.chunker import (
    IMAGE_ENDPOINT_PREFIX,
    PAGE_IMAGES_BASE_DIR,
    DoclingBackend,
    DocumentChunker,
    build_image_urls,
)

__all__ = [
    "IMAGE_ENDPOINT_PREFIX",
    "PAGE_IMAGES_BASE_DIR",
    "DoclingBackend",
    "DocumentChunker",
    "build_image_urls",
]
