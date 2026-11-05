"""LocalFile + ChromaDB dataset type binding.

No field is editable after creation. The binding adds one cross-axis
rule: manual ingest honours the source's extension allow-list.
"""

from __future__ import annotations

from typing import ClassVar

from syft_space.components.dataset_types.chromadb_local_binding import (
    ChromaDBLocalBinding,
)
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.sources.local_file.local_file_source import (
    LocalFileProvider,
)


class LocalFileChromaDBDatasetType(ChromaDBLocalBinding):
    """Local files indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "local_file"
    SOURCE_PROVIDER_CLS: ClassVar[type[LocalFileProvider]] = LocalFileProvider

    @classmethod
    def description(cls) -> str:
        """Get the description of the binding."""
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the binding."""
        return "🎨"

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Enforce the source's extension allow-list, then ingest.

        The source already filters its own change stream by extension;
        this guard covers manual ingest paths where the caller supplies
        the file list directly.
        """
        allowed = self.source.allowed_extensions()
        for file in request.files:
            ext = file.path.suffix.lower()
            if ext not in allowed:
                raise ValueError(f"Unsupported file type: {ext}")
        await self.vector_store.ingest(ctx, request)


__all__ = ["LocalFileChromaDBDatasetType"]
