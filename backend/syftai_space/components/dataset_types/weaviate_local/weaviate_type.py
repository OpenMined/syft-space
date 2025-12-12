"""Weaviate dataset type implementation."""

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from syftai_space.components.dataset_types.interfaces import (
    FileIngestableDatasetType,
    IngestFile,
    IngestRequest,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from syftai_space.components.shared.domain_types import (
    Context,
    HealthcheckResponse,
    HealthcheckStatus,
)

try:
    import weaviate
    from docling.document_converter import DocumentConverter, DocumentStream
    from weaviate.classes.config import Configure
    from weaviate.classes.query import MetadataQuery

    enabled = True
except ImportError:
    enabled = False

DEFAULT_SIMILARITY_THRESHOLD = 0.5
DEFAULT_HTTP_PORT = 8083
DEFAULT_GRPC_PORT = 50051

DEFAULT_INGEST_FILE_TYPE_OPTIONS = [".pdf", ".txt", ".html", ".xlsx", ".docx", ".md"]


class LocalFileDatasetType(FileIngestableDatasetType):
    """Local file dataset type that allows you to store and query your data.

    It uses the weaviate vector database to store and query your data.
    Implements FileIngestableDatasetType for watch-based file ingestion.
    """

    NAME = "local_file"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Local file dataset type.

        Args:
            config: Configuration dictionary with connection settings
        """
        self.config = config
        self.config["httpPort"] = config.get("httpPort", DEFAULT_HTTP_PORT)
        self.config["grpcPort"] = config.get("grpcPort", DEFAULT_GRPC_PORT)
        if enabled:
            self.converter = DocumentConverter()

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
        return "🕸️"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this dataset type.

        Returns:
            JSON schema describing configuration requirements
        """
        return {
            "type": "object",
            "properties": {
                "collectionName": {
                    "type": "string",
                    "title": "Collection Name",
                    "description": "The name of the weaviate collection to ingest the data into",
                },
                "ingestFileTypeOptions": {
                    "type": "array",
                    "title": "Ingest File Type Options",
                    "items": {
                        "type": "string",
                        "enum": [".pdf", ".txt", ".html", ".xlsx", ".docx", ".md"],
                    },
                    "uniqueItems": True,
                    "default": [".pdf", ".txt", ".html", ".xlsx", ".docx", ".md"],
                },
                "filePaths": {
                    "type": "array",
                    "title": "File Paths",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "title": "File Path",
                            },
                            "description": {
                                "type": "string",
                                "title": "Description",
                            },
                        },
                        "required": ["path", "description"],
                    },
                    "uniqueItems": True,
                    "default": [],
                },
            },
            "required": ["collectionName", "filePaths"],
        }

    def watched_paths(self) -> list[str]:
        """Get the paths to watch for new files.

        Extracts paths from the filePaths configuration.

        Returns:
            List of absolute directory/file paths to monitor.
        """
        return [
            path
            for file_path_item in self.config.get("filePaths", [])
            if isinstance(file_path_item, dict)
            and (path := file_path_item.get("path")) is not None
        ]

    def allowed_extensions(self) -> set[str]:
        """Get the allowed file extensions for ingestion.

        Extracts extensions from the ingestFileTypeOptions configuration.

        Returns:
            Set of extensions including the dot (e.g., {".pdf", ".txt"}).
        """
        return set(
            self.config.get("ingestFileTypeOptions", DEFAULT_INGEST_FILE_TYPE_OPTIONS)
        )

    @classmethod
    def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the dataset type.

        Args:
            configuration: Configuration dictionary to validate
        """

        # TODO: Maybe use Pydantic model to validate configuration

        # Check if required fields are present
        if "collectionName" not in configuration:
            raise ValueError("collectionName is required")

        # Validate collectionName,
        # it can only contain letters, numbers, and underscores (_), and spaces are not allowed.
        if not re.match(r"^[a-zA-Z0-9_]+$", configuration["collectionName"]):
            raise ValueError(
                "collectionName can only contain letters, numbers, and underscores (_), "
                "and spaces are not allowed."
            ) from None

        # Check if filePaths exist
        for file_path_item in configuration["filePaths"]:
            # Handle both old format (string) and new format (object with path and description)
            if isinstance(file_path_item, str):
                file_path = file_path_item
            elif isinstance(file_path_item, dict):
                file_path = file_path_item.get("path")
                if not file_path:
                    raise ValueError("filePaths item must have a 'path' property")
                if "description" not in file_path_item:
                    raise ValueError(
                        "filePaths item must have a 'description' property"
                    )
            else:
                raise ValueError(
                    f"filePaths item must be a string or object with 'path' and 'description' properties, got {type(file_path_item)}"
                )

            if not Path(file_path).exists():
                raise ValueError(f"filePaths does not exist: {file_path}")

    def _parse_document(self, file: IngestFile) -> dict[str, Any]:
        """Parse the document into a dictionary.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with parsed document content and metadata
        """
        # Convert the file to a document stream
        stream = BytesIO(file.file_handle.read())
        document_stream = DocumentStream(name=file.filename, stream=stream)
        conv_result = self.converter.convert(document_stream)

        # Return the parsed document content and metadata
        return {
            "content": conv_result.document.export_to_markdown(),
            "file_name": file.filename,
            "file_type": file.content_type,
            "file_size": file.file_size or 0,
        }

    def ingest(self, ctx: Context, request: IngestRequest) -> None:
        """Ingest files into Weaviate.

        Args:
            ctx: Request context with sender information
            request: Ingest request with files to process
        """
        if not enabled:
            raise ImportError("Weaviate and docling are required for ingestion")

        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            # Ensure collection exists
            if not client.collections.exists(self.config["collectionName"]):
                client.collections.create(
                    self.config["collectionName"],
                    vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
                )

        # Ingest the data into the data source
        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            collection = client.collections.get(self.config["collectionName"])
            for file in request.files:
                if file.content_type not in self.allowed_extensions():
                    raise ValueError(
                        f"Unsupported file type: {file.content_type}"
                    ) from None
                parsed_document = self._parse_document(file)
                collection.data.insert(parsed_document)

    def search(
        self, ctx: Context, query: str, params: Optional[SearchParameters] = None
    ) -> SearchResult:
        """Search the dataset for the given query.

        Args:
            ctx: Request context with sender information
            query: Search query string
            params: Optional search parameters

        Returns:
            SearchResult with matching documents
        """
        if not enabled:
            raise ImportError("Weaviate is required for search")

        if params is None:
            params = SearchParameters()

        documents = []

        similarity_threshold = (
            params.similarity_threshold
            if params.similarity_threshold
            else DEFAULT_SIMILARITY_THRESHOLD
        )

        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            collection = client.collections.get(self.config["collectionName"])

            results = collection.query.near_text(
                query=query,
                limit=params.limit,
                certainty=similarity_threshold,
                return_metadata=MetadataQuery(
                    distance=True, score=True, creation_time=True
                ),
            )
            for result in results.objects:
                documents.append(
                    SearchedDocument(
                        document_id=str(result.uuid),
                        content=result.properties.get("content", ""),
                        metadata={
                            "creation_time": str(result.metadata.creation_time),
                            "distance": result.metadata.distance,
                            "file_name": result.properties.get("file_name", ""),
                        },
                        similarity_score=result.metadata.score or 0.0,
                    )
                )

        return SearchResult(documents=documents, metadata={"count": len(documents)})

    @classmethod
    def enabled(cls) -> bool:
        """Check if this dataset type is enabled.

        Returns:
            True if weaviate and docling are installed
        """
        return enabled

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Return list of connection-related configuration fields.

        These fields are shared across all datasets of this type.
        - httpPort, grpcPort: Server connection settings
        - useTLS: Connection security setting

        Dataset-specific fields (not included):
        - queryLimit: query limit setting
        - collectionName: Each dataset has its own collection
        - ingestFileTypeOptions: Per-dataset ingestion settings
        """
        return ["httpPort", "grpcPort", "useTLS"]

    def healthcheck(self) -> HealthcheckResponse:
        """Check if the dataset type is healthy.

        Returns:
            HealthcheckResponse indicating health status
        """
        if not enabled:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="Weaviate dependencies not installed",
            )

        try:
            with weaviate.connect_to_local(
                port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
            ) as client:
                if client.is_ready():
                    return HealthcheckResponse(
                        status=HealthcheckStatus.HEALTHY, message="Weaviate is healthy"
                    )
        except Exception as e:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message=f"Weaviate is unhealthy: {str(e)}",
            )

        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY, message="Weaviate is unhealthy"
        )
