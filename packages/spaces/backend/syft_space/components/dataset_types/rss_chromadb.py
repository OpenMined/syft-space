"""RSS + ChromaDB dataset type binding.

Nothing here is secret, so the default redaction applies: a private feed's
token rides in its URL, not in a credential field of its own.
"""

from __future__ import annotations

from typing import ClassVar

from syft_space.components.dataset_types.chromadb_local_binding import (
    ChromaDBLocalBinding,
)
from syft_space.components.sources.rss.rss_source import RssProvider


class RssChromaDBDatasetType(ChromaDBLocalBinding):
    """Items from public RSS or Atom feeds indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "rss"
    SOURCE_PROVIDER_CLS: ClassVar[type[RssProvider]] = RssProvider

    @classmethod
    def description(cls) -> str:
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        return "📡"


__all__ = ["RssChromaDBDatasetType"]
