"""Vector store protocols.

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
"""

from typing import Any, ClassVar, Protocol

from syft_space.components.shared.domain_types import HealthcheckResponse
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.shared.search_types import (
    SearchContext,
    SearchParameters,
    SearchResult,
)

__all__ = [
    "BaseVectorStore",
    "BaseVectorStoreProvisioner",
    "IngestableVectorStore",
]


class BaseVectorStoreProvisioner(Protocol):
    """Lifecycle manager for the infrastructure a vector store depends on.

    Provisioners are stateless: all methods are classmethods, all state is
    passed in as a dict and persisted in the ``provisioner_state`` row.
    Concrete provisioners cover things like "start a chroma subprocess",
    "create a Weaviate collection", etc.

    A vector store class points at its provisioner via
    ``PROVISIONER_CLS``; vector stores that need no infrastructure leave
    that attribute as ``None``.
    """

    NAME: ClassVar[str]

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        ...

    @classmethod
    async def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start/provision the resource.

        Args:
            config: Configuration for the resource.

        Returns:
            State dictionary with persistent identifiers needed to
            re-discover and manage the resource after restart.
        """
        ...

    @classmethod
    async def stop(cls, state: dict[str, Any]) -> None:
        """Stop the provisioned resource."""
        ...

    @classmethod
    async def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if the resource is currently running.

        Uses ``state`` to re-discover the resource (important after restart).
        """
        ...

    @classmethod
    async def wait_until_ready(cls, state: dict[str, Any]) -> None:
        """Wait until the provisioned resource is ready to accept connections.

        Default is a no-op in concrete subclasses that don't need a
        startup health check.
        """
        ...

    @classmethod
    async def status(cls, state: dict[str, Any]) -> str:
        """Get the detailed status of the resource."""
        ...


class BaseVectorStore(Protocol):
    """Base vector store interface.

    Covers the read path and lifecycle. Read-only or externally-managed
    vector stores implement this directly; vector stores that also
    accept ingest from this process implement ``IngestableVectorStore``.

    ``PROVISIONER_CLS`` points at the infrastructure manager that the
    vector store needs (e.g. a chroma subprocess provisioner). Leave
    it as ``None`` for vector stores that need no provisioning
    (externally-managed clusters).
    """

    NAME: ClassVar[str]
    PROVISIONER_CLS: ClassVar[type[BaseVectorStoreProvisioner] | None] = None

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
    """Vector store that accepts ingest / delete from this process."""

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Ingest the files in ``request`` into the underlying store."""
        ...

    async def delete(self, ctx: IngestContext) -> None:
        """Delete the dataset's content from the underlying store."""
        ...
