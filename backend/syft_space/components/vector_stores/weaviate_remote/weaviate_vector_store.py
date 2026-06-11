"""Remote Weaviate vector store implementation.

Read-only client over a remote Weaviate cluster. Implements
``BaseVectorStore`` (search + healthcheck) but not the ingestable
variant — Weaviate is fed externally; this process only queries.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.shared.search_types import (
    SearchContext,
    SearchedDocument,
    SearchParameters,
    SearchResult,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator
from syft_space.components.vector_stores.weaviate_remote.filters import (
    build_filter_node,
)
from syft_space.components.vector_stores.weaviate_remote.schemas import (
    DEFAULT_SIMILARITY_THRESHOLD,
    RemoteWeaviateVectorStoreConfiguration,
)

try:
    import weaviate
    from weaviate.classes.init import Auth
    from weaviate.classes.query import Filter, MetadataQuery

    enabled = True
except ImportError:
    enabled = False


class WeaviateVectorStore:
    """Remote Weaviate vector store — search and healthcheck only.

    The cluster is provisioned outside this process, so there is no
    ``PROVISIONER_CLS``; the binding's provisioner step is skipped at
    dataset creation time.
    """

    NAME = "weaviate_remote"
    PROVISIONER_CLS = None

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Weaviate remote vector store.

        Args:
            config: Connection + content/metadata mapping + filters.
        """
        self.config = RemoteWeaviateVectorStoreConfiguration.model_validate(config)

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
        return "🌐"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this vector store."""
        return RemoteWeaviateVectorStoreConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the vector store configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        try:
            config = RemoteWeaviateVectorStoreConfiguration.model_validate(
                configuration
            )
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Validate filters can be built into Weaviate filter objects
        if config.filters and enabled:
            try:
                instance = cls(configuration)
                instance._build_weaviate_filters()
            except Exception as e:
                raise ValueError(f"Invalid filter configuration: {e}") from e

    @classmethod
    def enabled(cls) -> bool:
        """Whether weaviate is importable."""
        return enabled

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Configuration fields shared across datasets of this type."""
        return ["http_url", "grpc_url", "api_key", "collection_name"]

    @property
    def collection_name(self) -> str:
        """Get the name of the collection."""
        return self.config.collection_name

    def _build_weaviate_filters(self) -> Any:
        """Build Weaviate Filter objects from configured filter conditions."""
        if not self.config.filters:
            return None
        return build_filter_node(self.config.filters, Filter)

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the Weaviate collection for matching items."""
        if not enabled:
            raise ImportError("Weaviate is required for search")

        if params is None:
            params = SearchParameters()

        documents = []

        similarity_threshold = (
            params.similarity_threshold
            if params.similarity_threshold is not None
            else DEFAULT_SIMILARITY_THRESHOLD
        )

        async with weaviate.use_async_with_custom(
            http_host=self.config.http_url.host,
            http_port=self.config.http_url.port,
            http_secure=self.config.http_url.scheme == "https",
            grpc_host=self.config.grpc_url.host,
            grpc_port=self.config.grpc_url.port,
            grpc_secure=self.config.grpc_url.scheme == "https",
            auth_credentials=Auth.api_key(self.config.api_key),
            headers=self.config.headers,
        ) as client:
            collection = client.collections.get(self.collection_name)
            weaviate_filters = self._build_weaviate_filters()

            results = await collection.query.near_text(
                query=query,
                limit=params.limit,
                certainty=similarity_threshold,
                filters=weaviate_filters,
                return_metadata=MetadataQuery(
                    distance=True, score=True, creation_time=True
                ),
            )
            for result in results.objects:
                if self.config.content_property:
                    content = str(
                        result.properties.get(self.config.content_property, "")
                    )
                else:
                    content = json.dumps(result.properties, default=str)

                if self.config.metadata_properties is not None:
                    custom_metadata = {
                        k: v
                        for k, v in result.properties.items()
                        if k in self.config.metadata_properties
                    }
                else:
                    custom_metadata = dict(result.properties)

                metadata = {
                    "creation_time": (
                        str(result.metadata.creation_time)
                        if result.metadata.creation_time
                        else None
                    ),
                    "distance": result.metadata.distance,
                    **custom_metadata,
                }

                documents.append(
                    SearchedDocument(
                        document_id=str(result.uuid),
                        content=content,
                        metadata=metadata,
                        similarity_score=result.metadata.score or 0.0,
                    )
                )

        return SearchResult(documents=documents, metadata={"count": len(documents)})

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the Weaviate server is reachable."""
        if not enabled:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="Weaviate dependencies not installed",
            )

        try:
            async with weaviate.use_async_with_custom(
                http_host=self.config.http_url.host,
                http_port=self.config.http_url.port,
                http_secure=self.config.http_url.scheme == "https",
                grpc_host=self.config.grpc_url.host,
                grpc_port=self.config.grpc_url.port,
                grpc_secure=self.config.grpc_url.scheme == "https",
                auth_credentials=Auth.api_key(self.config.api_key),
                headers=self.config.headers,
            ) as client:
                if await client.is_ready():
                    return HealthcheckResponse(
                        status=HealthcheckStatus.HEALTHY,
                        message="Weaviate is healthy",
                    )
        except Exception as e:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message=f"Weaviate is unhealthy: {str(e)}",
            )

        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY,
            message="Weaviate is unhealthy",
        )
