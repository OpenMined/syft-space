"""LocalFile + ChromaDB dataset type binding.

Pairs the local filesystem source with an embedded ChromaDB vector
store. ``split_config`` maps the flat user configuration into the
per-axis configs; ``BaseDatasetType`` handles instantiation and the
default lifecycle delegation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.interfaces import IngestableDatasetType
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.local_file.local_file_source import (
    FilePathItem,
    LocalFileProvider,
)
from syft_space.components.vector_stores.chromadb_local.chromadb_vector_store import (
    ChromaDBLocalVectorStore,
)
from syft_space.components.vector_stores.chromadb_local.schemas import (
    DEFAULT_HTTP_PORT,
)

DEFAULT_INGEST_FILE_TYPE_OPTIONS = [
    ".pdf",
    ".txt",
    ".html",
    ".xlsx",
    ".docx",
    ".md",
    ".csv",
    ".json",
]


class ChromaDBLocalConfiguration(BaseModel):
    """User-facing configuration for the local_file binding.

    A single flat shape that ``split_config`` divides into the source
    config and the vector store config at construction time.
    """

    collection_name: str = Field(
        ...,
        alias="collectionName",
        description="Name of the ChromaDB collection (alphanumeric and underscores only)",
    )
    http_port: int = Field(
        default=DEFAULT_HTTP_PORT,
        alias="httpPort",
        description="ChromaDB server HTTP port",
    )
    ingest_file_type_options: list[str] = Field(
        default=DEFAULT_INGEST_FILE_TYPE_OPTIONS,
        alias="ingestFileTypeOptions",
        description="Allowed file extensions for ingestion",
    )
    file_paths: list[FilePathItem] = Field(
        default_factory=list,
        alias="filePaths",
        description="List of file paths with descriptions to watch for ingestion",
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


class LocalFileChromaDBDatasetType(IngestableDatasetType):
    """Local files indexed in an embedded ChromaDB instance."""

    NAME: ClassVar[str] = "local_file"
    SOURCE_PROVIDER_CLS: ClassVar[type[LocalFileProvider]] = LocalFileProvider
    VECTOR_STORE_CLS: ClassVar[type[ChromaDBLocalVectorStore]] = (
        ChromaDBLocalVectorStore
    )

    @classmethod
    def split_config(
        cls, configuration: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate flat configuration into (source_cfg, vector_store_cfg)."""
        cfg = ChromaDBLocalConfiguration.model_validate(configuration)
        source_cfg = {
            "file_paths": [fp.model_dump() for fp in cfg.file_paths],
            "allowed_extensions": list(cfg.ingest_file_type_options),
        }
        vector_store_cfg = {
            "collection_name": cfg.collection_name,
            "http_port": cfg.http_port,
        }
        return source_cfg, vector_store_cfg

    @classmethod
    def selection_to_config(cls, items: list[tuple[str, str | None]]) -> dict[str, Any]:
        """Render picks as the flat ``filePaths`` shape."""
        return {
            "filePaths": [
                {"path": item_id, "description": description or ""}
                for item_id, description in items
            ]
        }

    @classmethod
    def description(cls) -> str:
        """Get the description of the binding."""
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the binding."""
        return "🎨"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the combined (source + vector store) configuration schema."""
        return ChromaDBLocalConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the combined configuration.

        Generates a ``collectionName`` if one wasn't supplied, runs the
        flat Pydantic schema, and then delegates to the per-axis
        validators (which check that the configured file paths exist).

        Raises:
            ValueError: If configuration is invalid.
        """
        if not configuration.get("collectionName") and not configuration.get(
            "collection_name"
        ):
            configuration["collectionName"] = uuid.uuid4().hex

        try:
            ChromaDBLocalConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        await super().validate_configuration(configuration)

    @property
    def collection_name(self) -> str:
        """Get the (prefixed) collection name from the vector store."""
        return self.vector_store.collection_name

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Enforce the source's extension allow-list, then ingest.

        The source already filters its own change stream by extension;
        this guard covers manual ingest paths where the caller supplies
        the file list directly.
        """
        allowed = self.source.allowed_extensions()
        for file in request.files:
            ext = file.path.suffix.lower()
            if ext not in allowed:
                raise ValueError(f"Unsupported file type: {ext}")
        await self.vector_store.ingest(ctx, request)


__all__ = [
    "ChromaDBLocalConfiguration",
    "DEFAULT_INGEST_FILE_TYPE_OPTIONS",
    "LocalFileChromaDBDatasetType",
]
