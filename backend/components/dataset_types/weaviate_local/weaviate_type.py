"""Weaviate dataset type implementation."""

from io import BytesIO
from typing import Any, Optional

from pydantic import ValidationError

from components.dataset_types.interfaces import (
    BaseDatasetType,
    IngestFile,
    IngestRequest,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from components.shared.domain_types import (
    Context,
    HealthcheckResponse,
    HealthcheckStatus,
)

try:
    import weaviate
    from docling.document_converter import DocumentConverter, DocumentStream
    from weaviate.classes.query import MetadataQuery

    enabled = True
except ImportError:
    enabled = False


class WeaviateLocalDatasetType(BaseDatasetType):
    """Weaviate is a vector database that allows you to store and query your data.

    It uses transformers to embed your data and then allows you to query it using
    a similarity search.

    Reference: https://weaviate.io/
    Docs: https://weaviate.io/developers/weaviate/
    """

    NAME = "weaviate_local"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Weaviate dataset type.

        Args:
            config: Configuration dictionary with connection settings
        """
        self.config = config
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
                "httpPort": {
                    "type": "number",
                    "title": "Localhost HTTP Port",
                    "default": 8080,
                },
                "grpcPort": {
                    "type": "number",
                    "title": "Localhost gRPC Port",
                    "default": 50051,
                },
                "useTLS": {
                    "type": "boolean",
                    "title": "Use TLS/HTTPS",
                    "default": False,
                },
                "collectionName": {
                    "type": "string",
                    "title": "Default Collection/Class Name",
                },
                "ingestFileTypeOptions": {
                    "type": "array",
                    "title": "Ingest File Type Options",
                    "items": {
                        "type": "string",
                    },
                    "default": [".pdf", ".txt", ".html", ".xlsx", ".docx", ".md"],
                },
                "queryLimit": {
                    "type": "number",
                    "title": "Query Limit",
                    "default": 10,
                },
            },
            "required": ["httpPort", "grpcPort", "collectionName"],
            "order": [
                "httpPort",
                "grpcPort",
                "useTLS",
                "collectionName",
                "ingestFileTypeOptions",
                "queryLimit",
            ],
        }

    @classmethod
    def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the dataset type.

        Args:
            configuration: Configuration dictionary to validate
        """

        # TODO: Maybe use Pydantic model to validate configuration

        # Check if required fields are present
        if "httpPort" not in configuration:
            raise ValidationError("httpPort is required")
        if "grpcPort" not in configuration:
            raise ValidationError("grpcPort is required")
        if "collectionName" not in configuration:
            raise ValidationError("collectionName is required")

        # Check if httpPort and grpcPort are positive
        if configuration["httpPort"] <= 0:
            raise ValidationError("httpPort must be positive")
        if configuration["grpcPort"] <= 0:
            raise ValidationError("grpcPort must be positive")

        # Check if queryLimit is positive
        if configuration.get("queryLimit", 10) <= 0:
            raise ValidationError("queryLimit must be positive")

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
                client.collections.create(self.config["collectionName"])

        # Ingest the data into the data source
        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            collection = client.collections.get(self.config["collectionName"])
            for file in request.files:
                collection.data.insert(self._parse_document(file))

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

        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            collection = client.collections.get(self.config["collectionName"])
            results = collection.query.near_text(
                query=query,
                limit=params.limit,
                return_metadata=MetadataQuery(distance=True, score=True),
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
