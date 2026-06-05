"""LocalFile + ChromaDB dataset type binding.

Composes a ``LocalFileSource`` (data origin) with a
``ChromaDBLocalVectorStore`` (vector storage). The class declares the
two collaborators via ``SOURCE_CLS`` / ``VECTOR_STORE_CLS`` and a
``split_config()`` classmethod that maps the flat user configuration to
each axis; ``BaseDatasetType.__init__`` handles instantiation and
default lifecycle delegation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.interfaces import (
    IngestableDatasetType,
    IngestContext,
    IngestRequest,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.sources.local_file.local_file_source import (
    FilePathItem,
    LocalFileSource,
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
    """Flat user-facing configuration for the local_file binding.

    ``split_config`` translates this into the per-axis configs at
    construction time.
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
    SOURCE_CLS: ClassVar[type[LocalFileSource]] = LocalFileSource
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

        Generates a ``collectionName`` if missing, then runs the combined
        Pydantic schema (covers cross-axis constraints) and per-axis
        validators (which check file paths exist, etc.).

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
        """Enforce the source's extension allow-list, then delegate.

        The source filters its own change stream by extension; this
        guard covers manual ingest paths where the file list is supplied
        by a caller rather than emitted by the source.
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
