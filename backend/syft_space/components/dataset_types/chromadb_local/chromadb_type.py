"""ChromaDB local dataset type implementation."""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from functools import lru_cache
from pathlib import Path as SyncPath
from types import ModuleType
from typing import Any

from anyio import Path as AsyncPath
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator

from syft_space.components.dataset_types.chunking import (
    DocumentChunker,
    build_image_urls,
)
from syft_space.components.dataset_types.interfaces import (
    FileIngestableDatasetType,
    IngestContext,
    IngestRequest,
    SearchContext,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator

try:
    from chromadb.errors import NotFoundError as _ChromaNotFoundError
except ImportError:
    _ChromaNotFoundError = None


def _import_chromadb() -> ModuleType:
    try:
        import chromadb

        return chromadb
    except ImportError as e:
        raise ImportError("chromadb required") from e


def _import_embedding_fn():
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        return ONNXMiniLM_L6_V2
    except ImportError as e:
        raise ImportError("chromadb required for embeddings") from e


@lru_cache
def _chromadb_available() -> bool:
    try:
        _import_chromadb()
        return True
    except ImportError:
        return False


DEFAULT_HTTP_PORT = 8100
DEFAULT_SIMILARITY_THRESHOLD = 0.5

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
    """Local ChromaDB dataset type for storing and querying vectorized data.

    Uses ChromaDB vector database in server mode with persistent storage.
    Implements FileIngestableDatasetType for watch-based file ingestion.
    """

    NAME = "local_file"

    # Class-level lock for thread-safe lazy initialization
    _embedding_fn_lock = threading.Lock()

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize ChromaDB local dataset type.

        Args:
            config: Configuration dictionary with connection settings
        """
        self.raw_config = config
        self.config = ChromaDBLocalConfiguration.model_validate(config)

        # Lazy initialization (instance-level)
        self._embedding_fn = None
        self._client: chromadb.AsyncClientAPI | None = None  # noqa: F821
        self._client_lock = asyncio.Lock()  # Instance-level lock for client

        # Shared chunking pipeline
        self._document_chunker = DocumentChunker()

    async def get_client(self) -> chromadb.AsyncClientAPI:  # noqa: F821
        """Get or create the ChromaDB async client.

        Uses a cached client instance to avoid connection accumulation.
        Thread-safe via async lock.
        """
        chromadb = _import_chromadb()

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

        return "localhost"

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

        Args:
            configuration: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid
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
        ONNXMiniLM_L6_V2 = _import_embedding_fn()

        if self._embedding_fn is None:
            with self._embedding_fn_lock:
                if self._embedding_fn is None:
                    self._embedding_fn = ONNXMiniLM_L6_V2()
        return self._embedding_fn(texts)

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Ingest files into ChromaDB collection as chunks.

        Each file is parsed into multiple chunks via the shared DocumentChunker.
        Each chunk is stored as a separate vector with metadata linking back
        to the source document and page numbers.

        Args:
            ctx: Ingest context with dataset identifier
            request: Ingest request with files to process
        """
        if not _chromadb_available():
            raise ImportError("ChromaDB is required for ingestion")

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

            # Run CPU-bound parsing in executor to avoid blocking event loop
            chunks = await asyncio.to_thread(
                self._document_chunker.parse_document,
                file,
                self.collection_name,
            )

            await self._store_chunks(collection, chunks)

    async def _store_chunks(self, collection, chunks: list[dict]) -> None:
        """Embed and store chunks with neighbor references in ChromaDB.

        Each chunk gets prev/next pointers so the search method can fetch
        surrounding context in a single batch call.
        """
        if not chunks:
            return

        doc_id = chunks[0]["doc_id"]
        chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

        for i, chunk in enumerate(chunks):
            prev_chunk_id = chunk_ids[i - 1] if i > 0 else ""
            next_chunk_id = chunk_ids[i + 1] if i < len(chunks) - 1 else ""

            embeddings = await asyncio.to_thread(
                self._generate_embeddings, [chunk["embedding_text"]]
            )

            await collection.add(
                ids=[chunk_ids[i]],
                documents=[chunk["text"]],
                embeddings=embeddings,
                metadatas=[
                    {
                        "doc_id": doc_id,
                        "chunk_index": i,
                        "prev_chunk_id": prev_chunk_id,
                        "next_chunk_id": next_chunk_id,
                        "file_name": chunk["file_name"],
                        "file_type": chunk["file_type"] or "",
                        "file_size": chunk["file_size"],
                        "page_numbers": ",".join(map(str, chunk["page_numbers"])),
                        "headings": " > ".join(chunk["headings"]),
                        "picture_ids": ",".join(chunk["picture_ids"]),
                    }
                ],
            )

    def _process_query_results(
        self,
        results: dict,
        dataset_id: str,
        similarity_threshold: float,
    ) -> tuple[list[SearchedDocument], set[str]]:
        """Convert raw ChromaDB query results into SearchedDocuments.

        Applies similarity threshold filtering and builds image URLs.

        Returns:
            Tuple of (matched documents, set of matched chunk IDs).
        """
        documents: list[SearchedDocument] = []
        matched_ids: set[str] = set()

        if not results["ids"] or not results["ids"][0]:
            return documents, matched_ids

        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0.0

            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            similarity_score = 1.0 - (distance / 2.0)

            if similarity_score <= similarity_threshold:
                continue

            matched_ids.add(doc_id)
            content = results["documents"][0][i] if results["documents"] else ""
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}

            # Add image URLs to metadata
            metadata["image_urls"] = build_image_urls(
                dataset_id,
                metadata.get("doc_id", ""),
                metadata.get("picture_ids", ""),
            )

            documents.append(
                SearchedDocument(
                    document_id=doc_id,
                    content=content,
                    metadata=metadata,
                    similarity_score=similarity_score,
                )
            )

        return documents, matched_ids

    @staticmethod
    async def _enrich_with_neighbor_context(
        collection,
        documents: list[SearchedDocument],
        matched_ids: set[str],
    ) -> None:
        """Fetch prev/next chunk text and attach to each matched document.

        Skips neighbors that are themselves already in the matched set
        to avoid redundant content.
        """
        neighbor_ids: set[str] = set()
        for doc in documents:
            for key in ("prev_chunk_id", "next_chunk_id"):
                nid = doc.metadata.get(key, "")
                if nid and nid not in matched_ids:
                    neighbor_ids.add(nid)

        neighbor_map: dict[str, str] = {}
        if neighbor_ids:
            neighbors = await collection.get(
                ids=list(neighbor_ids),
                include=["documents"],
            )
            if neighbors["ids"]:
                for nid, ndoc in zip(
                    neighbors["ids"], neighbors["documents"] or [], strict=False
                ):
                    neighbor_map[nid] = ndoc or ""

        for doc in documents:
            doc.metadata["prev_context"] = neighbor_map.get(
                doc.metadata.get("prev_chunk_id", ""), ""
            )
            doc.metadata["next_context"] = neighbor_map.get(
                doc.metadata.get("next_chunk_id", ""), ""
            )

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the ChromaDB collection for matching chunks.

        Returns top-k matching chunks enriched with neighboring chunk text
        for better RAG context. Image URLs use dataset_id to avoid leaking
        internal collection names.

        Args:
            ctx: Search context with dataset identifier
            query: Search query string
            params: Optional search parameters

        Returns:
            SearchResult with matching document chunks
        """
        if not _chromadb_available():
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

            try:
                collection = await client.get_collection(name=self.collection_name)
            except Exception:
                return SearchResult(
                    documents=[],
                    metadata={"count": 0, "error": "Collection not found"},
                )

            query_embedding = await asyncio.to_thread(
                self._generate_embeddings, [query]
            )

            results = await collection.query(
                query_embeddings=query_embedding,
                n_results=params.limit,
                include=["documents", "metadatas", "distances"],
            )

            documents, matched_ids = self._process_query_results(
                results, ctx.dataset_id, similarity_threshold
            )

            if documents:
                await self._enrich_with_neighbor_context(
                    collection, documents, matched_ids
                )

            return SearchResult(documents=documents, metadata={"count": len(documents)})

        except Exception as e:
            return SearchResult(
                documents=[],
                metadata={"count": 0, "error": str(e)},
            )

    @classmethod
    def enabled(cls) -> bool:
        """Check if this dataset type is enabled.

        Returns:
            True if chromadb is installed
        """
        return _chromadb_available()

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

        if not _chromadb_available():
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

    async def delete(self, ctx: IngestContext) -> None:
        """Delete the entire ChromaDB collection and its page images.

        Since each dataset owns its own collection, deletion drops the
        entire collection rather than filtering by dataset_id.

        Args:
            ctx: Ingest context with dataset identifier
        """
        if not _chromadb_available():
            raise ImportError("ChromaDB is required for deletion")

        client = await self.get_client()

        try:
            await client.delete_collection(name=self.collection_name)
        except Exception as e:
            # Collection may not exist if no documents were ever ingested
            if _ChromaNotFoundError and isinstance(e, _ChromaNotFoundError):
                logger.info(
                    f"Collection '{self.collection_name}' does not exist, "
                    "skipping deletion"
                )
            else:
                raise ValueError(f"Error deleting collection: {str(e)}") from e

        # Remove all page images for this collection
        await asyncio.to_thread(
            self._document_chunker.purge_page_images,
            self.collection_name,
        )
