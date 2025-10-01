import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from components.data_sources.interfaces import DataSource, Context, register_data_source
from components.data_sources.schemas import (
    SearchParameters,
    SearchResult,
    SearchedDocument,
    HealthcheckResponse,
    HealthcheckStatus,
)


try:
    import weaviate
    from weaviate.classes.query import MetadataQuery
    from docling.document_converter import DocumentConverter

    enabled = True
except ImportError:
    enabled = False


class Weaviate(DataSource):
    """Weaviate data source."""

    SOURCE_NAME = "weaviate"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.converter = DocumentConverter()

    @classmethod
    def configuration_schema(cls) -> Dict[str, Any]:
        """Return a dictionary of config values required by this data source provider.
        This will be displayed in the frontend/sdk as configurable values
        when creating a service.
        """
        return {
            "type": "object",
            "properties": {
                "httpPort": {
                    "number": "string",
                    "title": "Localhost HTTP Port",
                },
                "grpcPort": {
                    "type": "number",
                    "title": "Localhost gRPC Port",
                },
                "useTLS": {
                    "type": "boolean",
                    "title": "Use TLS/HTTPS",
                    "default": False,
                },
                "collection": {
                    "type": "string",
                    "title": "Default Collection/Class Name",
                },
                "ingestionPath": {
                    "type": "string",
                    "title": "Ingestion Path",
                },
                "ingestFileTypeOptions": {
                    "type": "array",
                    "title": "Ingest File Type Options",
                    "items": {
                        "type": "string",
                    },
                    "default": ["pdf", "txt", "html", "xlsx", "docx", "md"],
                },
                "queryLimit": {
                    "type": "number",
                    "title": "Query Limit",
                    "default": 10,
                },
            },
            "required": ["httpPort", "grpcPort", "collectionName", "ingestionPath"],
            "order": [
                "httpPort",
                "grpcPort",
                "useTLS",
                "collectionName",
                "ingestionPath",
                "ingestFileTypeOptions",
                "queryLimit",
            ],
        }

    def _parse_document(self, file_path: Path) -> Dict[str, Any]:
        """Parse the document into a dictionary."""
        conv_result = self.converter.convert(file_path)
        document = conv_result.document.export_to_markdown()
        return {
            "content": document,
            "file_name": file_path.name,
            "file_type": file_path.suffix[1:],
            "file_path": file_path.as_posix(),
        }

    def ingest(self, ctx: Context, data: List[Dict[str, Any]]) -> None:
        """Ingest the data into the data source."""

        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            # Check if the collection exists, if not create it
            exists = client.collections.exists(self.config["collectionName"])
            if not exists:
                client.collections.create(self.config["collectionName"])

        # Create the ingestion path if it doesn't exist
        ingestion_path = Path(self.config["ingestionPath"])
        ingestion_path.mkdir(parents=True, exist_ok=True)

        # Ingest the data into the data source
        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            collection = client.collections.use(self.config["collectionName"])
            for document in ingestion_path.iterdir():
                if (
                    document.is_file()
                    and document.suffix.lower() in self.config["ingestFileTypeOptions"]
                ):
                    collection.data.insert(self._parse_document(document))

    def search(
        self, ctx: Context, query: str, params: Optional[SearchParameters] = None
    ) -> SearchResult:
        """Search the data source for the given query."""
        documents = []

        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            questions = client.collections.use(self.config["collectionName"])
            results = questions.query.near_text(
                query=query,
                limit=params.limit,
                return_metadata=MetadataQuery(distance=True, score=True),
            )

            for result in results.objects:
                documents.append(
                    SearchedDocument(
                        document_id=result.uuid,
                        content=result.properties["content"],
                        metadata={
                            "creation_time": result.metadata.creation_time,
                            "distance": result.metadata.distance,
                            "file_name": result.properties["file_name"],
                        },
                        similarity_score=result.metadata.score,
                    )
                )

        return SearchResult(
            documents=documents,
            cost=0.0,
            search_engine=self.SOURCE_NAME,
            api_version="1.0.0",
        )

    @classmethod
    def enabled(cls) -> bool:
        return enabled

    def healthcheck(self) -> HealthcheckResponse:
        with weaviate.connect_to_local(
            port=self.config["httpPort"], grpc_port=self.config["grpcPort"]
        ) as client:
            if client.is_ready():
                return HealthcheckResponse(
                    status=HealthcheckStatus.HEALTHY, message="Weaviate is healthy"
                )
        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY, message="Weaviate is unhealthy"
        )


register_data_source(Weaviate)
