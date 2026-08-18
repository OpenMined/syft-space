"""Remote Weaviate dataset type binding.

Search-only binding over a remote Weaviate cluster. The cluster is
populated outside this process, so the source is a no-op; this
binding provides search and healthcheck and intentionally has no
ingest or delete path.
"""

from __future__ import annotations

from typing import Any, ClassVar

from syft_space.components.dataset_types.interfaces import BaseDatasetType
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.noop_source import NoOpProvider
from syft_space.components.vector_stores.weaviate_remote.schemas import (
    RemoteWeaviateVectorStoreConfiguration,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

# Re-export so the public configuration name stays stable.
RemoteWeaviateConfiguration = RemoteWeaviateVectorStoreConfiguration


class RemoteWeaviateDatasetType(BaseDatasetType):
    """Read-only binding over a remote Weaviate cluster.

    Use the Weaviate vector database to query data hosted on a remote
    Weaviate server. The cluster is populated outside this process; this
    binding provides search only.
    """

    NAME: ClassVar[str] = "remote_weaviate"
    SOURCE_PROVIDER_CLS: ClassVar[type[NoOpProvider]] = NoOpProvider
    VECTOR_STORE_CLS: ClassVar[type[WeaviateVectorStore]] = WeaviateVectorStore

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send the whole configuration to the vector store; the source needs none."""
        return {}, dict(configuration)

    @classmethod
    def description(cls) -> str:
        """Get the description of the binding."""
        return (
            "Remote Weaviate dataset type that allows you to query your data "
            "from a remote Weaviate server.\n\n"
            "It uses the Weaviate vector database to query your data from a "
            "remote server."
        )

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the binding."""
        return "🌐"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the vector store's configuration schema."""
        return RemoteWeaviateVectorStoreConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @property
    def collection_name(self) -> str:
        """Get the collection name from the vector store."""
        return self.vector_store.collection_name


__all__ = [
    "RemoteWeaviateConfiguration",
    "RemoteWeaviateDatasetType",
]
