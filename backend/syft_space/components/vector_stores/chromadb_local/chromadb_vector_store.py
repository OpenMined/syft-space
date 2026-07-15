"""ChromaDB local vector store implementation.

Owns chunking, embedding, and chroma I/O for a single collection.
Composed by ``LocalFileChromaDBDatasetType`` in ``dataset_types/``,
which provides the source half of the binding.
"""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache
from types import ModuleType
from typing import Any

from loguru import logger
from pydantic import ValidationError

from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.shared.ingest_types import IngestContext, IngestRequest
from syft_space.components.shared.search_types import (
    SearchContext,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.vector_stores.chromadb_local.external_provisioner import (
    ExternalChromaDBProvisioner,
)
from syft_space.components.vector_stores.chromadb_local.provisioner import (
    LocalChromaDBProvisioner,
)
from syft_space.components.vector_stores.chromadb_local.schemas import (
    ChromaDBLocalVectorStoreConfiguration,
)
from syft_space.components.vector_stores.chunking import (
    DocumentChunker,
    build_image_urls,
)
from syft_space.components.vector_stores.interfaces import BaseVectorStoreProvisioner
from syft_space.config import app_settings

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


DEFAULT_SIMILARITY_THRESHOLD = 0.5

# Embedding model — same as Weaviate (all-MiniLM-L6-v2).
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ChromaDB rejects a single add() larger than its max batch size (~5461).
# A large file (e.g. a CSV chunked per row) easily exceeds it, so writes are
# split into batches comfortably under that ceiling.
_ADD_BATCH_SIZE = 5000


def _resolve_provisioner_cls() -> type[BaseVectorStoreProvisioner]:
    """Resolve the provisioner from ``SYFT_CHROMADB_PROVISION``.

    Local mode manages a ``chroma run`` subprocess; external mode only
    ensures the space's database exists and tracks server health.
    """
    if app_settings.chromadb_provision:
        return LocalChromaDBProvisioner
    return ExternalChromaDBProvisioner


class ChromaDBLocalVectorStore:
    """ChromaDB vector store.

    Connects to the server configured via ``SYFT_CHROMADB_*`` settings —
    by default a process-local ``chroma run`` subprocess, or an
    externally managed server when ``SYFT_CHROMADB_PROVISION=false``.
    Owns one collection per dataset.
    """

    NAME = "chromadb_local"
    PROVISIONER_CLS = _resolve_provisioner_cls()

    # Class-level lock for thread-safe lazy embedding-model init.
    _embedding_fn_lock = threading.Lock()

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize ChromaDB local vector store.

        Args:
            config: Vector store configuration (``collection_name``,
                ``http_port``).
        """
        self.raw_config = config
        self.config = ChromaDBLocalVectorStoreConfiguration.model_validate(config)

        # Lazy initialization (instance-level)
        self._embedding_fn = None
        self._client: chromadb.AsyncClientAPI | None = None  # noqa: F821
        self._client_lock = asyncio.Lock()
        self._document_chunker = DocumentChunker()

    @classmethod
    def name(cls) -> str:
        """Get the name of the vector store."""
        return cls.NAME

    @classmethod
    def type(cls) -> str:
        """Get the type identifier of the vector store."""
        return cls.NAME.lower()

    @classmethod
    def description(cls) -> str:
        """Get the description of the vector store."""
        return cls.__doc__ or ""

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the vector store."""
        return "🎨"

    @classmethod
    def host(cls) -> str:
        """Get the host of the ChromaDB server."""
        return app_settings.chromadb_host

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the vector store's narrow configuration schema."""
        return ChromaDBLocalVectorStoreConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the vector store configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        try:
            ChromaDBLocalVectorStoreConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

    @classmethod
    def enabled(cls) -> bool:
        """Whether chromadb is importable."""
        return _chromadb_available()

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Configuration fields shared across all collections."""
        return ["httpPort"]

    @property
    def collection_name(self) -> str:
        """Get the (prefixed) name of the ChromaDB collection."""
        return f"Collection_{self.config.collection_name}"

    async def get_client(self) -> chromadb.AsyncClientAPI:  # noqa: F821
        """Get or create the cached ChromaDB async client."""
        chromadb = _import_chromadb()

        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = await chromadb.AsyncHttpClient(
                        host=self.host(),
                        port=self.config.http_port,
                        ssl=app_settings.chromadb_ssl,
                        database=app_settings.chromadb_database,
                    )
        return self._client

    def _generate_embeddings(self, texts: list[str]) -> list:
        """Generate embeddings for texts (runs in thread pool).

        Thread-safe lazy initialization keeps model loading off the
        event loop.
        """
        ONNXMiniLM_L6_V2 = _import_embedding_fn()

        if self._embedding_fn is None:
            with self._embedding_fn_lock:
                if self._embedding_fn is None:
                    self._embedding_fn = ONNXMiniLM_L6_V2()
        return self._embedding_fn(texts)

    async def ingest(self, ctx: IngestContext, request: IngestRequest) -> None:
        """Ingest files into the collection as embedded chunks.

        Each file is parsed into multiple chunks via the shared
        ``DocumentChunker``; each chunk is stored as a separate vector
        with metadata linking back to the source document and page
        numbers.
        """
        if not _chromadb_available():
            raise ImportError("ChromaDB is required for ingestion")

        client = await self.get_client()
        collection = await client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        for file in request.files:
            chunks = await asyncio.to_thread(
                self._document_chunker.parse_document,
                file,
                self.collection_name,
            )
            await self._store_chunks(collection, chunks)

    async def _store_chunks(self, collection, chunks: list[dict]) -> None:
        """Embed and store chunks with neighbor references in ChromaDB.

        Each chunk gets prev/next pointers so the search method can
        fetch surrounding context in a single batch call.
        """

        # Early return if no chunks to store.
        if not chunks:
            return

        # Get the document ID and number of chunks.
        doc_id = chunks[0]["doc_id"]
        num_chunks = len(chunks)
        chunk_ids = [f"{doc_id}_{i}" for i in range(num_chunks)]

        # Embed all chunks in one call.
        embeddings = await asyncio.to_thread(
            self._generate_embeddings, [chunk["embedding_text"] for chunk in chunks]
        )

        # Build metadata for all chunks.
        metadatas = [
            {
                "doc_id": doc_id,
                "chunk_index": i,
                "prev_chunk_id": chunk_ids[i - 1] if i > 0 else "",
                "next_chunk_id": chunk_ids[i + 1] if i < num_chunks - 1 else "",
                "file_name": chunk["file_name"],
                "file_type": chunk["file_type"] or "",
                "file_size": chunk["file_size"],
                "page_numbers": ",".join(map(str, chunk["page_numbers"])),
                "headings": " > ".join(chunk["headings"]),
                "picture_ids": ",".join(chunk["picture_ids"]),
            }
            for i, chunk in enumerate(chunks)
        ]

        # Write in batches under ChromaDB's max add() size (see _ADD_BATCH_SIZE).
        documents = [chunk["text"] for chunk in chunks]
        for start in range(0, num_chunks, _ADD_BATCH_SIZE):
            end = start + _ADD_BATCH_SIZE
            await collection.add(
                ids=chunk_ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
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
            # ChromaDB cosine distance: 0 = identical, 2 = opposite.
            similarity_score = 1.0 - (distance / 2.0)

            if similarity_score <= similarity_threshold:
                continue

            matched_ids.add(doc_id)
            content = results["documents"][0][i] if results["documents"] else ""
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}

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

        Skips neighbors already in the matched set.
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
        """Search the collection for matching chunks."""
        if not _chromadb_available():
            raise ImportError("ChromaDB is required for search")

        if params is None:
            params = SearchParameters()

        similarity_threshold = (
            params.similarity_threshold
            if params.similarity_threshold is not None
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

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the ChromaDB server is reachable."""
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
        """Delete the entire collection and its page images.

        Since each dataset owns its own collection, deletion drops the
        full collection rather than filtering by dataset_id.
        """
        if not _chromadb_available():
            raise ImportError("ChromaDB is required for deletion")

        client = await self.get_client()

        try:
            await client.delete_collection(name=self.collection_name)
        except Exception as e:
            if _ChromaNotFoundError and isinstance(e, _ChromaNotFoundError):
                logger.info(
                    f"Collection '{self.collection_name}' does not exist, "
                    "skipping deletion"
                )
            else:
                raise ValueError(f"Error deleting collection: {str(e)}") from e

        await asyncio.to_thread(
            self._document_chunker.purge_page_images,
            self.collection_name,
        )
