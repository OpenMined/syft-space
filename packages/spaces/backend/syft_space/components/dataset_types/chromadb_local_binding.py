"""Base for bindings whose vector store is the embedded ChromaDB.

Holds what the ChromaDB-backed bindings share: the store class, the
``collectionName`` default, and the prefixed collection name. A concrete
binding adds its source, name, icon and description.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from syft_space.components.dataset_types.interfaces import IngestableDatasetType
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)


class ChromaDBLocalBinding(IngestableDatasetType):
    """A source paired with the embedded ChromaDB vector store."""

    VECTOR_STORE_CLS: ClassVar[type[ChromaDBLocalVectorStore]] = (
        ChromaDBLocalVectorStore
    )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Generate a ``collectionName`` if missing, then validate per axis."""
        if not configuration.get("collectionName") and not configuration.get(
            "collection_name"
        ):
            configuration["collectionName"] = uuid.uuid4().hex
        await super().validate_configuration(configuration)

    @property
    def collection_name(self) -> str:
        """The (prefixed) collection name from the vector store."""
        return self.vector_store.collection_name


__all__ = ["ChromaDBLocalBinding"]
