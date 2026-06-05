"""Remote Weaviate vector store package."""

from syft_space.components.vector_stores.weaviate_remote.schemas import (
    RemoteWeaviateVectorStoreConfiguration,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

__all__ = [
    "RemoteWeaviateVectorStoreConfiguration",
    "WeaviateVectorStore",
]
