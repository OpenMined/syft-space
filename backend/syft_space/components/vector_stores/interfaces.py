"""Vector store interfaces.

A ``BaseVectorStore`` is responsible for vector storage and search of a
dataset's content. It is orthogonal to ``BaseSource`` (data origin):
any source can feed any ``IngestableVectorStore``, and any vector store
can be queried regardless of where the content came from.

Bindings between a source and a vector store live in ``dataset_types/``.

Two tiers exist so read-only / externally-managed vector stores
(e.g. a Weaviate cluster you don't ingest into from this process) don't
have to implement ingest/delete:

- ``BaseVectorStore``: search + healthcheck + lifecycle.
- ``IngestableVectorStore``: adds ``ingest`` and ``delete`` on top.

Shared domain models (``IngestFile``, ``IngestRequest``, ``IngestContext``,
``SearchContext``, ``SearchParameters``, ``SearchResult``) continue to
live in ``dataset_types/interfaces.py`` for now and are re-exported here
so vector store implementations can depend on a single module.
"""

from typing import Any, Protocol

from syft_space.components.dataset_types.interfaces import (
    IngestContext,
    IngestRequest,
    SearchContext,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.domain_types import HealthcheckResponse

__all__ = [
    "BaseVectorStore",
    "IngestableVectorStore",
    # re-exports
    "IngestContext",
    "IngestRequest",
    "SearchContext",
    "SearchParameters",
    "SearchResult",
]


class BaseVectorStore(Protocol):
    """Base vector store interface.

    Covers the read path and lifecycle. Read-only or externally-managed
    vector stores implement this directly; vector stores that also
    accept ingest from this process implement ``IngestableVectorStore``.
    """

    NAME: str

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the vector store with configuration."""
        ...

    @classmethod
    def name(cls) -> str:
        """Get the name of the vector store."""
        ...

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the vector store."""
        ...

    @classmethod
    def description(cls) -> str:
        """Get the description of the vector store."""
        ...

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the vector store."""
        ...

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this vector store."""
        ...

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the vector store.

        Raises:
            ValueError: If configuration is invalid.
        """
        ...

    @classmethod
    def enabled(cls) -> bool:
        """Whether this vector store's optional dependencies are installed."""
        ...

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Configuration field names that are connection-related.

        Shared across all datasets of a given dataset_type when using a
        shared provisioner. See ``BaseDatasetType.connection_fields``.
        """
        ...

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the vector store for matches to ``query``."""
        ...

    async def healthcheck(self) -> HealthcheckResponse:
        """Report whether the underlying store is reachable / healthy."""
        ...


class IngestableVectorStore(BaseVectorStore, Protocol):
    """Vector store that accepts ingest / delete from this process.

    Extends ``BaseVectorStore`` with the write path. Implementations
    chunk and embed ``IngestFile`` payloads internally.
    """

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Ingest the files in ``request`` into the underlying store."""
        ...

    async def delete(self, ctx: IngestContext) -> None:
        """Delete the dataset's content from the underlying store."""
        ...
