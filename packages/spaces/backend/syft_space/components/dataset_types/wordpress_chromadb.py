"""WordPress + ChromaDB dataset type binding.

The source flags its Application Password as secret, so the default
redaction drops it.
"""

from __future__ import annotations

from typing import ClassVar

from syft_space.components.dataset_types.chromadb_local_binding import (
    ChromaDBLocalBinding,
)
from syft_space.components.sources.wordpress.wordpress_source import WordPressProvider


class WordPressChromaDBDatasetType(ChromaDBLocalBinding):
    """WordPress posts and pages indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "wordpress"
    SOURCE_PROVIDER_CLS: ClassVar[type[WordPressProvider]] = WordPressProvider

    @classmethod
    def description(cls) -> str:
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        return "📰"


__all__ = ["WordPressChromaDBDatasetType"]
