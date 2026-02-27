"""Shared document chunking pipeline using Docling.

Provides a unified parse → chunk → save images pipeline used by all
dataset types (ChromaDB, Weaviate, etc.). Each dataset type handles
its own DB-specific storage and retrieval.
"""

import shutil
import threading
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from syft_space.components.dataset_types.interfaces import IngestFile

# Page images stored at ~/.syft-space/page_images/{collection_name}/{doc_id}/
PAGE_IMAGES_BASE_DIR = Path.home() / ".syft-space" / "page_images"

# API route prefix for serving document images
IMAGE_ENDPOINT_PREFIX = "/api/v1/datasets"


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

        Configured with picture extraction so embedded figures can be
        saved to disk separately. Page renders are not generated.
        Thread-safe via double-checked locking.
        """
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        if DocumentChunker._converter is None:
            with self._converter_lock:
                if DocumentChunker._converter is None:
                    pipeline_options = PdfPipelineOptions(
                        generate_picture_images=True,
                    )
                    DocumentChunker._converter = DocumentConverter(
                        format_options={
                            InputFormat.PDF: PdfFormatOption(
                                pipeline_options=pipeline_options
                            )
                        }
                    )
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

    def parse_document(
        self, file: IngestFile, collection_name: str
    ) -> list[dict[str, Any]]:
        """Parse document into chunks with metadata and save images to disk.

        Uses Docling for PDFs and other rich formats (DOCX, XLSX, HTML, etc.)
        with HybridChunker for tokenizer-aware chunking. Plain text/JSON files
        are handled directly without Docling overhead.

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
        stream = BytesIO(file.file_handle.read())
        ext = Path(file.filename).suffix.lower()
        doc_id = uuid4().hex[:16]

        # Simple text files - no Docling overhead needed
        if ext in [".json", ".txt"]:
            content = stream.read().decode("utf-8")
            return [
                {
                    "text": content,
                    "embedding_text": content,
                    "doc_id": doc_id,
                    "page_numbers": [],
                    "headings": [],
                    "picture_ids": [],
                    "file_name": file.filename,
                    "file_type": file.content_type,
                    "file_size": file.file_size or 0,
                }
            ]

        # All other formats via Docling
        from docling.datamodel.base_models import DocumentStream

        stream.seek(0)
        source = DocumentStream(name=file.filename, stream=stream)
        result = self.converter.convert(source)
        doc = result.document
        images_dir = self.get_page_images_dir(collection_name, doc_id)
        images_dir.mkdir(parents=True, exist_ok=True)

        # Save extracted pictures and map to pages
        picture_page_map: dict[int, list[str]] = {}
        for picture in doc.pictures:
            pil_image = picture.get_image(doc)
            if pil_image:
                pic_filename = f"{uuid4().hex}.png"
                pil_image.save(images_dir / pic_filename, "PNG")
                if picture.prov:
                    for prov in picture.prov:
                        picture_page_map.setdefault(prov.page_no, []).append(
                            pic_filename
                        )

        # Chunk the document
        chunker = self.chunker
        chunks = []
        for chunk in chunker.chunk(doc):
            # Extract page numbers from chunk provenance
            page_numbers = sorted(
                {
                    prov.page_no
                    for item in chunk.meta.doc_items
                    for prov in (item.prov or [])
                }
            )

            # Collect picture IDs for this chunk's pages
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
                    "file_name": file.filename,
                    "file_type": file.content_type,
                    "file_size": file.file_size or 0,
                }
            )

        return chunks

    def purge_page_images(self, collection_name: str) -> None:
        """Purge all page images for a collection."""
        page_images_dir = PAGE_IMAGES_BASE_DIR / collection_name
        if page_images_dir.exists():
            shutil.rmtree(page_images_dir)
