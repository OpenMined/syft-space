"""Remote Weaviate dataset type binding.

Composes a ``NoOpSource`` (no data origin — the Weaviate cluster is
fed externally) with a ``WeaviateVectorStore`` (search over a remote
cluster). Read-only: no ingest / delete.
"""

from __future__ import annotations

from typing import Any, ClassVar

from syft_space.components.dataset_types.interfaces import BaseDatasetType
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
    """Read-only binding over a remote Weaviate cluster.

    Use the Weaviate vector database to query data hosted on a remote
    Weaviate server. The cluster is populated outside this process; this
    binding provides search only.
    """

    NAME: ClassVar[str] = "remote_weaviate"
    SOURCE_CLS: ClassVar[type[NoOpSource]] = NoOpSource
    VECTOR_STORE_CLS: ClassVar[type[WeaviateVectorStore]] = WeaviateVectorStore

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """NoOpSource takes no config; Weaviate takes the whole thing."""
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
