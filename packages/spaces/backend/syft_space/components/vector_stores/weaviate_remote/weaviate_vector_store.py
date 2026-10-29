"""Remote Weaviate vector store implementation.

Read-only client over a remote Weaviate cluster. Implements
``BaseVectorStore`` (search + healthcheck) but not the ingestable
variant — Weaviate is fed externally; this process only queries.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from syft_space.components.shared import client_cache
from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)
from syft_space.components.shared.metadata_types import MetadataField, MetadataFields
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
    RemoteWeaviateVectorStoreConfiguration,
)

try:
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Auth, Timeout
    from weaviate.classes.query import Filter, MetadataQuery
    from weaviate.exceptions import WeaviateClosedClientError, WeaviateConnectionError
    from weaviate.outputs.query import Object, WeaviateProperties

    enabled = True
except ImportError:
    enabled = False


def _document_metadata(
    result: Object[WeaviateProperties, None],
    config: RemoteWeaviateVectorStoreConfiguration,
) -> dict[str, Any]:
    """Metadata of one searched document: the store's own keys plus the
    properties the owner allowlisted in ``metadata_properties``. No
    allowlist, no properties."""
    allowed = config.metadata_properties or ()
    return {
        "creation_time": (
            str(result.metadata.creation_time)
            if result.metadata.creation_time
            else None
        ),
        "distance": result.metadata.distance,
        **{k: v for k, v in result.properties.items() if k in allowed},
    }


class WeaviateMetadataFields(MetadataFields):
    """Keys the owner allowlisted in ``metadata_properties``, plus the
    store's own ``creation_time``. ``distance`` and the content property are
    internal. With no allowlist nothing else is declared, so nothing else
    leaves.
    """

    def declared(self) -> tuple[MetadataField, ...]:
        public = tuple(
            MetadataField(name=n) for n in self.config.get("metadata_properties") or ()
        ) + (MetadataField(name="creation_time"),)
        hidden = [MetadataField(name="distance", hidden=True)]
        if content := self.config.get("content_property"):
            hidden.append(MetadataField(name=content, hidden=True))
        return public + tuple(hidden)


class WeaviateVectorStore:
    """Remote Weaviate vector store — search and healthcheck only.

    The cluster is provisioned outside this process, so there is no
    ``PROVISIONER_CLS``; the binding's provisioner step is skipped at
    dataset creation time.
    """

    NAME = "weaviate_remote"
    PROVISIONER_CLS = None
    METADATA_FIELDS = WeaviateMetadataFields

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
        """Configuration fields that identify the server connection."""
        return ["http_url", "grpc_url", "api_key", "headers"]

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

        client = await self.get_client()
        collection = client.collections.get(self.collection_name)
        weaviate_filters = self._build_weaviate_filters()

        try:
            results = await collection.query.near_text(
                query=query,
                limit=params.limit,
                certainty=params.similarity_threshold,
                filters=weaviate_filters,
                return_metadata=MetadataQuery(
                    distance=True, certainty=True, creation_time=True
                ),
            )
        except (WeaviateConnectionError, WeaviateClosedClientError):
            # Dead client: drop it so the next query reconnects.
            await client_cache.evict(self.NAME, self._client_key())
            raise

        for result in results.objects:
            if self.config.content_property:
                content = str(result.properties.get(self.config.content_property, ""))
            else:
                content = json.dumps(result.properties, default=str)

            metadata = _document_metadata(result, self.config)

            documents.append(
                SearchedDocument(
                    document_id=str(result.uuid),
                    content=content,
                    metadata=metadata,
                    # ``certainty`` is Weaviate's own 1 - distance/2 similarity;
                    # ``score`` is only set for BM25/hybrid, so it was always 0.0.
                    similarity_score=result.metadata.certainty or 0.0,
                )
            )

        return SearchResult(documents=documents, metadata={"count": len(documents)})

    CONNECT_TIMEOUT = 10.0
    HEALTHCHECK_TIMEOUT = 5.0

    def _client_key(self) -> tuple:
        # Keyed by ``connection_fields``, so a changed URL, key or header is
        # a miss rather than a stale client.
        return client_cache.key_from(self.config, self.connection_fields())

    async def get_client(self) -> Any:
        """The shared connected client for this store's connection config."""
        return await client_cache.get_client(
            self.NAME,
            self._client_key(),
            connect=self._connect,
            close=lambda client: client.close(),
        )

    async def _connect(self) -> Any:
        client = weaviate.use_async_with_custom(
            http_host=self.config.http_url.host,
            http_port=self.config.http_url.port,
            http_secure=self.config.http_url.scheme == "https",
            grpc_host=self.config.grpc_url.host,
            grpc_port=self.config.grpc_url.port,
            grpc_secure=self.config.grpc_url.scheme == "https",
            auth_credentials=Auth.api_key(self.config.api_key),
            headers=self.config.headers,
            additional_config=AdditionalConfig(
                timeout=Timeout(init=self.CONNECT_TIMEOUT)
            ),
        )
        await client.connect()
        return client

    def _ready_url(self) -> str:
        return f"{str(self.config.http_url).rstrip('/')}/v1/.well-known/ready"

    async def healthcheck(self) -> HealthcheckResponse:
        """Check if the Weaviate server is ready.

        A single GET of Weaviate's readiness probe. Opening a full client
        just to ask this costs an HTTP + gRPC handshake under the client's
        2 s init timeout, which fails at random under concurrent checks.
        """
        if not enabled:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message="Weaviate dependencies not installed",
            )

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            **(self.config.headers or {}),
        }
        try:
            async with httpx.AsyncClient(timeout=self.HEALTHCHECK_TIMEOUT) as client:
                response = await client.get(self._ready_url(), headers=headers)
        except Exception as e:
            return HealthcheckResponse(
                status=HealthcheckStatus.UNHEALTHY,
                message=f"Weaviate is unhealthy: {str(e)}",
            )

        if response.status_code == 200:
            return HealthcheckResponse(
                status=HealthcheckStatus.HEALTHY,
                message="Weaviate is healthy",
            )
        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY,
            message=f"Weaviate is unhealthy: ready probe returned {response.status_code}",
        )
