"""Vector store abstractions.

A ``BaseVectorStore`` stores and queries vectorized content. It is
orthogonal to ``BaseSource`` (data origin): bindings between the two
live in ``dataset_types/``.
"""

from syft_space.components.vector_stores.interfaces import (
    BaseVectorStore,
    BaseVectorStoreProvisioner,
    IngestableVectorStore,
)
from syft_space.components.vector_stores.registry import (
    VECTOR_STORE_REGISTRY,
    VectorStoreRegistry,
    register_builtin_vector_stores,
)

__all__ = [
    "VECTOR_STORE_REGISTRY",
    "BaseVectorStore",
    "BaseVectorStoreProvisioner",
    "IngestableVectorStore",
    "VectorStoreRegistry",
    "register_builtin_vector_stores",
]
