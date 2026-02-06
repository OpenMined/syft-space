"""ChromaDB local dataset type implementation."""

import asyncio
import hashlib
import os
import re
import threading
import uuid
from io import BytesIO
from pathlib import Path as SyncPath
from typing import Any

from anyio import Path as AsyncPath
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from syft_space.components.dataset_types.interfaces import (
    FileIngestableDatasetType,
    IngestFile,
    IngestRequest,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.domain_types import (
    Context,
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    enabled = True
except ImportError:
    enabled = False

DEFAULT_HTTP_PORT = 8100
DEFAULT_SIMILARITY_THRESHOLD = 0.65

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

# Embedding model - same as Weaviate (all-MiniLM-L6-v2)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class FilePathItem(BaseModel):
    """A file path item with path and description."""

    path: str = Field(..., description="The file or directory path to watch")
    description: str = Field(..., description="Description of the data at this path")


class ChromaDBLocalConfiguration(BaseModel):
    """Configuration for ChromaDB local dataset type."""

    collection_name: str | None = Field(
        default=None,
        alias="collectionName",
        description="Name of the ChromaDB collection (auto-generated if not provided)",
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

    @model_validator(mode="before")
    @classmethod
    def generate_collection_name_if_missing(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Auto-generate collection name if not provided."""
        if isinstance(data, dict):
            if "collectionName" not in data and "collection_name" not in data:
                data = dict(data)  # Avoid mutating input dict
                data["collectionName"] = uuid.uuid4().hex[:8]
            elif data.get("collectionName") is None and data.get("collection_name") is None:
                data = dict(data)
                data["collectionName"] = uuid.uuid4().hex[:8]
        return data

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
    """Local ChromaDB dataset type for storing and querying vectorized data.

    Uses ChromaDB vector database in server mode with persistent storage.
    Implements FileIngestableDatasetType for watch-based file ingestion.
    """

    NAME = "local_file"

    # Class-level locks for thread-safe lazy initialization (shared resources)
    _converter_lock = threading.Lock()
    _embedding_fn_lock = threading.Lock()

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize ChromaDB local dataset type.

        Args:
            config: Configuration dictionary with connection settings
        """
        self.raw_config = config
        self.config = ChromaDBLocalConfiguration.model_validate(config)

        if self.config.collection_name and "collectionName" not in self.raw_config:
            self.raw_config["collectionName"] = self.config.collection_name

        # Lazy initialization (instance-level)
        self._converter = None
        self._embedding_fn = None
        self._client: chromadb.AsyncClientAPI | None = None
        self._client_lock = asyncio.Lock()  # Instance-level lock for client

    @property
    def converter(self):
        """Lazily initialize DocumentConverter on first use.

        Thread-safe via double-checked locking.
        """
        from docling.document_converter import DocumentConverter

        if self._converter is None:
            with self._converter_lock:
                if self._converter is None:
                    self._converter = DocumentConverter()
        return self._converter

    async def get_client(self) -> "chromadb.AsyncClientAPI":
        """Get or create the ChromaDB async client.

        Uses a cached client instance to avoid connection accumulation.
        Thread-safe via async lock.
        """
        if not enabled:
            raise ImportError("chromadb required")

        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = await chromadb.AsyncHttpClient(
                        host=self.host(),
                        port=self.config.http_port,
                        ssl=False,
                    )
        return self._client

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
    def host(cls) -> str:
        """Get the host of the dataset type."""

        return os.getenv("DOCKER_NETWORK_HOST", "localhost")

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this dataset type.

        Returns:
            JSON schema describing configuration requirements
        """
        return ChromaDBLocalConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the dataset type.

        Note: This method intentionally mutates the configuration dict to persist
        the auto-generated collection_name. This is necessary so the same name
        is used across all instantiations from the stored config.

        Args:
            configuration: Configuration dictionary to validate (may be mutated)

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            config = ChromaDBLocalConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Persist generated collection_name back to config dict for storage
        if config.collection_name and "collectionName" not in configuration:
            configuration["collectionName"] = config.collection_name

        # Validate file paths exist
        for file_path_item in config.file_paths:
            path = AsyncPath(file_path_item.path)
            if not await path.exists():
                raise ValueError(f"filePaths does not exist: {file_path_item['path']}")

    def watched_paths(self) -> list[str]:
        """Get the paths to watch for new files.

        Returns:
            List of absolute directory/file paths to monitor.
        """
        return [item.path for item in self.config.file_paths]

    def allowed_extensions(self) -> set[str]:
        """Get the allowed file extensions for ingestion.

        Returns:
            Set of extensions including the dot (e.g., {".pdf", ".txt"}).
        """
        return set(self.config.ingest_file_type_options)

    @property
    def collection_name(self) -> str:
        """Get the name of the collection."""
        return f"Collection_{self.config.collection_name}"

    def _generate_embeddings(self, texts: list[str]) -> list:
        """Generate embeddings for texts (runs in thread pool).

        Thread-safe lazy initialization ensures model loading
        happens in the thread pool, not blocking the event loop.
        """
        if not enabled:
            raise ImportError("chromadb required for embeddings")

        if self._embedding_fn is None:
            with self._embedding_fn_lock:
                if self._embedding_fn is None:
                    self._embedding_fn = SentenceTransformerEmbeddingFunction(
                        model_name=EMBEDDING_MODEL
                    )
        return self._embedding_fn(texts)

    def _parse_document(self, file: IngestFile) -> dict[str, Any]:
        """Parse the document into a dictionary.

        Args:
            file: IngestFile to parse

        Returns:
            Dictionary with parsed document content and metadata
        """
        from docling.document_converter import DocumentStream

        # Convert the file to a document stream
        stream = BytesIO(file.file_handle.read())

        # If the file is a JSON or TXT file, read the content directly
        if SyncPath(file.filename).suffix.lower() in [".json", ".txt"]:
            content = stream.read().decode("utf-8")
        else:
            # Otherwise, convert the file to a document stream and export to markdown
            document_stream = DocumentStream(name=file.filename, stream=stream)
            conv_result = self.converter.convert(document_stream)
            content = conv_result.document.export_to_markdown()

        # Return the parsed document content and metadata
        return {
            "content": content,
            "file_name": file.filename,
            "file_type": file.content_type,
            "file_size": file.file_size or 0,
        }

    async def ingest(self, ctx: Context, request: IngestRequest) -> None:
        """Ingest files into ChromaDB collection.

        Args:
            ctx: Request context with sender information
            request: Ingest request with files to process
        """
        if not enabled:
            raise ImportError("ChromaDB and docling are required for ingestion")

        client = await self.get_client()

        # Get or create collection with cosine similarity
        collection = await client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        for file in request.files:
            ext = SyncPath(file.filename).suffix.lower()
            if ext not in self.allowed_extensions():
                raise ValueError(f"Unsupported file type: {ext}")

            # Run CPU-bound docling parsing in executor to avoid blocking event loop
            parsed_doc = await asyncio.to_thread(self._parse_document, file)

            # Generate embeddings in executor (CPU-bound)
            embeddings = await asyncio.to_thread(
                self._generate_embeddings, [parsed_doc["content"]]
            )

            # Generate unique ID based on filename and content hash
            doc_id = hashlib.sha256(
                f"{file.filename}:{parsed_doc['content'][:100]}".encode()
            ).hexdigest()[:32]

            # Add to collection
            await collection.add(
                ids=[doc_id],
                documents=[parsed_doc["content"]],
                embeddings=embeddings,
                metadatas=[
                    {
                        "file_name": parsed_doc["file_name"],
                        "file_type": parsed_doc["file_type"] or "",
                        "file_size": parsed_doc["file_size"],
                    }
                ],
            )

    async def search(
        self, ctx: Context, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the ChromaDB collection for similar documents.

        Args:
            ctx: Request context with sender information
            query: Search query string
            params: Optional search parameters

        Returns:
            SearchResult with matching documents
        """
        if not enabled:
            raise ImportError("ChromaDB is required for search")

        if params is None:
            params = SearchParameters()

        similarity_threshold = (
            params.similarity_threshold
            if params.similarity_threshold
            else DEFAULT_SIMILARITY_THRESHOLD
        )

        try:
            client = await self.get_client()

            # Try to get collection
            try:
                collection = await client.get_collection(name=self.collection_name)
            except Exception:
                # Collection doesn't exist
                return SearchResult(
                    documents=[],
                    metadata={"count": 0, "error": "Collection not found"},
                )

            # Generate query embedding in executor (CPU-bound)
            query_embedding = await asyncio.to_thread(
                self._generate_embeddings, [query]
            )

            # Query with embedding
            results = await collection.query(
                query_embeddings=query_embedding,
                n_results=params.limit,
                include=["documents", "metadatas", "distances"],
            )

            documents = []

            # Process results (ChromaDB returns nested lists)
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = (
                        results["distances"][0][i] if results["distances"] else 0.0
                    )

                    # Convert distance to similarity score
                    # ChromaDB cosine distance: 0 = identical, 2 = opposite
                    # Similarity = 1 - (distance / 2)
                    similarity_score = 1.0 - (distance / 2.0)

                    # Apply similarity threshold filter
                    if similarity_score < similarity_threshold:
                        continue

                    content = results["documents"][0][i] if results["documents"] else ""
                    metadata = (
                        results["metadatas"][0][i] if results["metadatas"] else {}
                    )

                    documents.append(
                        SearchedDocument(
                            document_id=doc_id,
                            content=content,
                            metadata=metadata,
                            similarity_score=similarity_score,
                        )
                    )

            return SearchResult(documents=documents, metadata={"count": len(documents)})

        except Exception as e:
            # Handle connection errors
            return SearchResult(
                documents=[],
                metadata={"count": 0, "error": str(e)},
            )

    @classmethod
    def enabled(cls) -> bool:
        """Check if this dataset type is enabled.

        Returns:
            True if chromadb and docling are installed
        """
        return enabled

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Return list of connection-related configuration fields.

        These fields are shared across all datasets of this type.
        - httpPort: Server connection port

        Dataset-specific fields (not included):
        - collectionName: Each dataset has its own collection
        - ingestFileTypeOptions: Per-dataset ingestion settings
        - filePaths: Per-dataset file paths
        """
        return ["httpPort"]

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the ChromaDB server is healthy.

        Returns:
            HealthcheckResponse indicating health status
        """
        heartbeat = None

        if not enabled:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="ChromaDB dependencies not installed",
            )

        try:
            client = await self.get_client()
            heartbeat = await client.heartbeat()

            if heartbeat:
                return HealthcheckResponse(
                    status=HealthcheckStatus.HEALTHY,
                    message="ChromaDB is healthy",
                )
        except Exception as e:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message=f"ChromaDB is unhealthy: {str(e)}",
            )

        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY,
            message="ChromaDB is unhealthy",
        )
