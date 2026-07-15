"""Configuration schema for the ChromaDB local vector store."""

import re

from pydantic import BaseModel, Field, field_validator

from syft_space.config import app_settings


def default_http_port() -> int:
    """Default ChromaDB port (``SYFT_CHROMADB_HTTP_PORT``)."""
    return app_settings.chromadb_http_port


class ChromaDBLocalVectorStoreConfiguration(BaseModel):
    """Configuration for the ChromaDB local vector store.

    Narrow vector-store-only config (no source-axis fields). The binding
    layer (``dataset_types/chromadb_local/``) carries the combined
    source + vector store schema and forwards the relevant subset here.
    """

    collection_name: str = Field(
        ...,
        alias="collectionName",
        description="Name of the ChromaDB collection (alphanumeric and underscores only)",
    )
    http_port: int = Field(
        default_factory=default_http_port,
        alias="httpPort",
        description="ChromaDB server HTTP port",
    )

    model_config = {"populate_by_name": True}

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v: str) -> str:
        """Validate collection name contains only allowed characters."""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "collection_name can only contain letters, numbers, and underscores"
            )
        return v
