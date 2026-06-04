"""Dataset type interfaces and domain models.

A ``BaseDatasetType`` is the binding of a ``BaseSource`` (data origin)
and a ``BaseVectorStore`` (vector storage). Concrete bindings declare
``SOURCE_CLS`` and ``VECTOR_STORE_CLS`` as class attributes plus a
``split_config()`` classmethod that translates the flat user-facing
configuration into the two per-axis configs; the default ``__init__``
takes care of constructing each collaborator and exposing them as
``self.source`` and ``self.vector_store``.

Lifecycle methods (``search``, ``healthcheck``, ``ingest``, ``delete``)
delegate to the collaborators by default; bindings only override when
they need cross-axis policy (e.g. a source-defined allow-list applied
at ingest time).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from syft_space.components.shared.domain_types import Context, HealthcheckResponse

if TYPE_CHECKING:
    from syft_space.components.sources.interfaces import BaseSource
    from syft_space.components.vector_stores.interfaces import (
        BaseVectorStore,
        IngestableVectorStore,
    )


class SearchContext(Context):
    """Context for search requests."""

    dataset_id: UUID = Field(..., description="Unique identifier for the dataset")


class IngestContext(Context):
    """Context for ingestion requests."""

    dataset_id: UUID = Field(..., description="Unique identifier for the dataset")


class SearchParameters(BaseModel):
    """Domain contract for search parameters."""

    similarity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Similarity threshold for matching"
    )
    limit: int = Field(
        default=5, ge=1, description="Maximum number of results to return"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the search"
    )


class SearchedDocument(BaseModel):
    """A single document from search results."""

    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score for the document"
    )


class SearchResult(BaseModel):
    """Domain contract for search results."""

    documents: list[SearchedDocument] = Field(
        default_factory=list, description="List of searched documents"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional search metadata"
    )


class IngestFile(BaseModel):
    """Framework-agnostic file wrapper for ingestion."""

    path: Path = Field(..., description="Local readable path")
    filename: str = Field(..., description="Display filename")
    file_size: int | None = Field(default=None, description="Size in bytes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata"
    )


class IngestRequest(BaseModel):
    """Domain contract for data ingestion."""

    files: list[IngestFile] = Field(
        default_factory=list, description="List of files to ingest"
    )


class BaseDatasetType:
    """Binding of a ``BaseSource`` with a ``BaseVectorStore``.

    Subclasses declare ``SOURCE_CLS`` / ``VECTOR_STORE_CLS`` class
    attributes plus a ``split_config()`` classmethod that produces the
    per-axis configs. The default ``__init__`` instantiates each
    collaborator; lifecycle methods delegate to them.
    """

    NAME: ClassVar[str]
    SOURCE_CLS: ClassVar[type[BaseSource]]
    VECTOR_STORE_CLS: ClassVar[type[BaseVectorStore]]

    source: BaseSource
    vector_store: BaseVectorStore

    def __init__(self, configuration: dict[str, Any]) -> None:
        """Construct the source + vector store from the flat user config.

        Args:
            configuration: User-facing configuration dictionary.
        """
        cls = type(self)
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        self.source = cls.SOURCE_CLS(source_cfg)
        self.vector_store = cls.VECTOR_STORE_CLS(vector_store_cfg)

    # ── Required per-binding ─────────────────────────────────────────

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate flat user configuration into per-axis configs.

        Returns:
            ``(source_config, vector_store_config)`` — each in the shape
            its constructor expects.
        """
        raise NotImplementedError

    @classmethod
    def description(cls) -> str:
        """Human-readable description of the binding."""
        raise NotImplementedError

    @classmethod
    def icon(cls) -> str:
        """Icon for the binding (display only)."""
        raise NotImplementedError

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the combined source + vector store configuration schema.

        Bindings own the user-facing schema because the public API is
        flat — the schema describes what the user types in, before
        ``split_config`` translates it.
        """
        raise NotImplementedError

    # ── Default classmethods (overridable) ───────────────────────────

    @classmethod
    def name(cls) -> str:
        """Get the name of the binding."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the binding."""
        return cls.NAME.lower()

    @classmethod
    def enabled(cls) -> bool:
        """A binding is enabled only if both collaborators are enabled."""
        return cls.SOURCE_CLS.enabled() and cls.VECTOR_STORE_CLS.enabled()

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Connection fields are shared across datasets of this type.

        Owned by the vector store — the provisioner records connection
        values once and overlays them onto every dataset created under
        this binding.
        """
        return cls.VECTOR_STORE_CLS.connection_fields()

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate by splitting and delegating to each collaborator.

        Bindings override when they need cross-axis or pre-split logic
        (e.g. defaulting a generated identifier before validation).

        Raises:
            ValueError: If configuration is invalid.
        """
        source_cfg, vector_store_cfg = cls.split_config(configuration)
        await cls.SOURCE_CLS.validate_configuration(source_cfg)
        await cls.VECTOR_STORE_CLS.validate_configuration(vector_store_cfg)

    # ── Default lifecycle (overridable) ──────────────────────────────

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Delegate search to the vector store."""
        return await self.vector_store.search(ctx, query, params)

    async def healthcheck(self) -> HealthcheckResponse:
        """Delegate healthcheck to the vector store."""
        return await self.vector_store.healthcheck()


class IngestableDatasetType(BaseDatasetType):
    """Binding whose vector store accepts ingest from this process.

    Read-only bindings (e.g. a Weaviate cluster fed externally) extend
    ``BaseDatasetType`` directly; bindings that ingest from this process
    extend ``IngestableDatasetType`` so the write-path defaults are
    available.
    """

    VECTOR_STORE_CLS: ClassVar[type[IngestableVectorStore]]
    vector_store: IngestableVectorStore

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Delegate ingest to the vector store."""
        await self.vector_store.ingest(ctx, request)

    async def delete(self, ctx: IngestContext) -> None:
        """Delegate delete to the vector store."""
        await self.vector_store.delete(ctx)


class BaseDatasetTypeProvisioner:
    """Base dataset type provisioner interface.

    Provisioners handle lifecycle management of dataset infrastructure.
    All methods are classmethods - provisioners are stateless.
    State is passed as parameters and stored in the ProvisionerState row.

    Provisioning is a vector-store concern; the registry currently keys
    provisioners by dataset-type name only because bindings are 1:1 with
    their vector store today. A follow-up moves provisioners under
    ``vector_stores/`` and re-keys ``provisioner_state`` accordingly.
    """

    NAME: ClassVar[str]

    @classmethod
    def name(cls) -> str:
        """Get the name of the provisioner."""
        return cls.NAME

    @classmethod
    async def start(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Start/provision the resource.

        Args:
            config: Configuration for the resource.

        Returns:
            State dictionary with persistent identifiers needed to
            re-discover and manage the resource after restart.
        """
        raise NotImplementedError

    @classmethod
    async def stop(cls, state: dict[str, Any]) -> None:
        """Stop the provisioned resource."""
        raise NotImplementedError

    @classmethod
    async def is_running(cls, state: dict[str, Any]) -> bool:
        """Check if resource is currently running.

        Uses state to re-discover the resource (important after restart).
        """
        raise NotImplementedError

    @classmethod
    async def wait_until_ready(cls, state: dict[str, Any]) -> None:
        """Wait until the provisioned resource is ready to accept connections.

        Default is a no-op. Override in subclasses that need startup
        health checks (e.g., HTTP server readiness).
        """
        return None

    @classmethod
    async def status(cls, state: dict[str, Any]) -> str:
        """Get detailed status of the resource."""
        raise NotImplementedError
