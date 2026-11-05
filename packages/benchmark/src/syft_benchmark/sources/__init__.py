"""The source of the original text.

Invariant 1: only this package sees the text of the Space's documents.
Everything further down the pipeline works with questions and gold answers.
"""

from syft_benchmark.sources.chroma import (
    ChromaClient,
    ChromaError,
    Chunk,
    Document,
    is_useful,
    load_documents,
    parse_date,
    strip_header,
)

__all__ = [
    "Chunk",
    "ChromaClient",
    "ChromaError",
    "Document",
    "is_useful",
    "load_documents",
    "parse_date",
    "strip_header",
]
