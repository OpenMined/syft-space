"""LocalFile + ChromaDB dataset type binding.

Composes a ``LocalFileSource`` (data origin) with a
``ChromaDBLocalVectorStore`` (vector storage) and delegates the
search/ingest/delete/healthcheck path to the vector store. The combined
``ChromaDBLocalConfiguration`` splits flat user input into the two
axis-specific configs.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from anyio import Path as AsyncPath
from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.interfaces import (
    FileIngestableDatasetType,
    IngestContext,
    IngestRequest,
    SearchContext,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.domain_types import HealthcheckResponse
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
    """Combined source + vector store config for the local_file binding.

    The binding splits this into the two axis-specific configs at
    ``__init__`` time.
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


class LocalFSChromaDBDatasetType(FileIngestableDatasetType):
    """Binding of ``LocalFileSource`` + ``ChromaDBLocalVectorStore``.

    Holds one instance of each axis and delegates ingest / search /
    delete / healthcheck to the vector store, watched-paths and
    extension queries to the source.
    """

    NAME = "local_file"

    def __init__(self, config: dict[str, Any]) -> None:
        self.raw_config = config
        self.config = ChromaDBLocalConfiguration.model_validate(config)
        self.source = LocalFileSource(
            {
                "file_paths": [fp.model_dump() for fp in self.config.file_paths],
                "allowed_extensions": list(self.config.ingest_file_type_options),
            }
        )
        self.vector_store = ChromaDBLocalVectorStore(
            {
                "collection_name": self.config.collection_name,
                "http_port": self.config.http_port,
            }
        )

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
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the dataset type."""
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

        Raises:
            ValueError: If configuration is invalid.
        """
        # Generate collectionName if not provided
        collection_name = configuration.get("collectionName") or configuration.get(
            "collection_name"
        )
        if collection_name is None:
            configuration["collectionName"] = uuid.uuid4().hex

        try:
            config = ChromaDBLocalConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Validate file paths exist
        for file_path_item in config.file_paths:
            path = AsyncPath(file_path_item.path)
            if not await path.exists():
                raise ValueError(f"filePaths does not exist: {file_path_item.path}")

    def watched_paths(self) -> list[str]:
        """Delegate to source."""
        return self.source.watched_paths()

    def allowed_extensions(self) -> set[str]:
        """Delegate to source."""
        return self.source.allowed_extensions()

    @property
    def collection_name(self) -> str:
        """Get the (prefixed) collection name from the vector store."""
        return self.vector_store.collection_name

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Validate file types against the source's allow-list, then delegate."""
        allowed = self.allowed_extensions()
        for file in request.files:
            ext = file.path.suffix.lower()
            if ext not in allowed:
                raise ValueError(f"Unsupported file type: {ext}")
        await self.vector_store.ingest(ctx, request)

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Delegate to vector store."""
        return await self.vector_store.search(ctx, query, params)

    async def healthcheck(self) -> HealthcheckResponse:
        """Delegate to vector store."""
        return await self.vector_store.healthcheck()

    async def delete(self, ctx: IngestContext) -> None:
        """Delegate to vector store."""
        await self.vector_store.delete(ctx)

    @classmethod
    def enabled(cls) -> bool:
        """Whether the underlying vector store's deps are installed."""
        return ChromaDBLocalVectorStore.enabled()

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Connection fields shared across datasets of this type."""
        return ChromaDBLocalVectorStore.connection_fields()


__all__ = [
    "ChromaDBLocalConfiguration",
    "DEFAULT_INGEST_FILE_TYPE_OPTIONS",
    "LocalFSChromaDBDatasetType",
]
