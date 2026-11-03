"""Blogspot + ChromaDB dataset type binding.

The source flags its API key as secret, so the default redaction drops it
while the blog URLs stay visible.
"""

from __future__ import annotations

from typing import ClassVar

from syft_space.components.dataset_types.chromadb_local_binding import (
    ChromaDBLocalBinding,
)
from syft_space.components.sources.blogspot.blogspot_source import BlogspotProvider


class BlogspotChromaDBDatasetType(ChromaDBLocalBinding):
    """Posts from public Blogspot blogs indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "blogspot"
    SOURCE_PROVIDER_CLS: ClassVar[type[BlogspotProvider]] = BlogspotProvider

    @classmethod
    def description(cls) -> str:
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        return "✍️"


__all__ = ["BlogspotChromaDBDatasetType"]
