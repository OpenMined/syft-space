"""Remote Weaviate dataset type binding.

Composes a ``NoOpSource`` (no-op data origin — Weaviate is fed
externally) with a ``WeaviateVectorStore`` (search over a remote
cluster). Search and healthcheck delegate to the vector store.
"""

from __future__ import annotations

from typing import Any

from syft_space.components.dataset_types.interfaces import (
    BaseDatasetType,
    SearchContext,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.domain_types import HealthcheckResponse
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.noop.noop_source import NoOpSource
from syft_space.components.vector_stores.weaviate_remote.schemas import (
    RemoteWeaviateVectorStoreConfiguration,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

# Re-export so the public configuration name stays stable.
RemoteWeaviateConfiguration = RemoteWeaviateVectorStoreConfiguration


class RemoteWeaviateDatasetType(BaseDatasetType):
    """Binding of ``NoOpSource`` + ``WeaviateVectorStore``.

    Weaviate is fed externally; this process only queries it. Search
    and healthcheck delegate to the vector store.
    """

    NAME = "remote_weaviate"

    def __init__(self, config: dict[str, Any]) -> None:
        self.source = NoOpSource({})
        self.vector_store = WeaviateVectorStore(config)
        # Kept for callers that still read .config on the dataset type.
        self.config = self.vector_store.config

    @classmethod
    def name(cls) -> str:
        """Get the name of the dataset type."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the dataset type."""
        return cls.NAME.lower()

    @classmethod
    def description(cls) -> str:
        """Get the description of the dataset type."""
        return (
            "Remote Weaviate dataset type that allows you to query your data "
            "from a remote Weaviate server.\n\n"
            "It uses the Weaviate vector database to query your data from a "
            "remote server."
        )

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the dataset type."""
        return "🌐"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the configuration schema from the vector store."""
        return RemoteWeaviateVectorStoreConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Delegate validation to the vector store."""
        await WeaviateVectorStore.validate_configuration(configuration)

    @property
    def collection_name(self) -> str:
        """Get the collection name from the vector store."""
        return self.vector_store.collection_name

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Delegate to vector store."""
        return await self.vector_store.search(ctx, query, params)

    @classmethod
    def enabled(cls) -> bool:
        """Whether the underlying vector store's deps are installed."""
        return WeaviateVectorStore.enabled()

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Connection fields shared across datasets of this type."""
        return WeaviateVectorStore.connection_fields()

    async def healthcheck(self) -> HealthcheckResponse:
        """Delegate to vector store."""
        return await self.vector_store.healthcheck()


__all__ = [
    "RemoteWeaviateConfiguration",
    "RemoteWeaviateDatasetType",
]
