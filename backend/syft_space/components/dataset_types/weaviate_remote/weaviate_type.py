"""RemoteWeaviate dataset type implementation."""

import json
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, HttpUrl, ValidationError, model_validator

from syft_space.components.dataset_types.interfaces import (
    BaseDatasetType,
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
    import weaviate
    from weaviate.classes.init import Auth
    from weaviate.classes.query import Filter, MetadataQuery

    enabled = True
except ImportError:
    enabled = False

DEFAULT_SIMILARITY_THRESHOLD = 0.5


class FilterOperator(str, Enum):
    """Comparison operators for property filters."""

    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"
    LIKE = "like"
    IS_NONE = "is_none"
    CONTAINS_ANY = "contains_any"
    CONTAINS_ALL = "contains_all"


class LogicalOperator(str, Enum):
    """Logical operators for combining filter conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"


class FilterCondition(BaseModel):
    """A single property filter condition."""

    type: Literal["condition"] = "condition"
    property: str = Field(..., description="Weaviate property name to filter on")
    op: FilterOperator = Field(..., description="Comparison operator")
    value: str | int | float | bool | list[str] = Field(
        ...,
        description="Value to compare against. Use a list for contains_any/contains_all.",
    )


class FilterGroup(BaseModel):
    """A group of conditions combined with a logical operator.

    Supports 1 level of nesting: operands can be conditions or sub-groups,
    but sub-groups can only contain conditions.
    """

    type: Literal["group"] = "group"
    op: LogicalOperator = Field(..., description="Logical operator to combine operands")
    operands: list[
        Annotated[Union[FilterCondition, "FilterGroup"], Field(discriminator="type")]
    ] = Field(..., description="Conditions or sub-groups to combine")

    @model_validator(mode="after")
    def validate_nesting_depth(self) -> "FilterGroup":
        """Ensure max 1 level of nesting."""
        for operand in self.operands:
            if isinstance(operand, FilterGroup):
                for inner in operand.operands:
                    if isinstance(inner, FilterGroup):
                        raise ValueError("Max 1 level of filter nesting allowed")
        return self


FilterGroup.model_rebuild()

WeaviateFilter = Annotated[FilterCondition | FilterGroup, Field(discriminator="type")]

OPERATOR_MAP: dict[FilterOperator, str] = {
    FilterOperator.EQUAL: "equal",
    FilterOperator.NOT_EQUAL: "not_equal",
    FilterOperator.GREATER_THAN: "greater_than",
    FilterOperator.GREATER_OR_EQUAL: "greater_or_equal",
    FilterOperator.LESS_THAN: "less_than",
    FilterOperator.LESS_OR_EQUAL: "less_or_equal",
    FilterOperator.LIKE: "like",
    FilterOperator.IS_NONE: "is_none",
    FilterOperator.CONTAINS_ANY: "contains_any",
    FilterOperator.CONTAINS_ALL: "contains_all",
}


class RemoteWeaviateConfiguration(BaseModel):
    """Configuration for Weaviate remote dataset type."""

    http_url: HttpUrl = Field(..., description="The HTTP URL of the Weaviate server")
    grpc_url: HttpUrl = Field(..., description="The gRPC URL of the Weaviate server.")
    api_key: str = Field(..., description="The API key for the Weaviate server")
    collection_name: str = Field(..., description="The name of the Weaviate collection")
    headers: dict[str, str] | None = Field(
        default=None,
        description="Additional HTTP headers for third-party API keys (e.g., {'X-Cohere-Api-Key': 'key', 'X-OpenAI-Api-Key': 'key'})",
        json_schema_extra={"secret": True},
    )
    default_similarity_threshold: float = Field(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        description="The default similarity threshold for the Weaviate collection",
    )
    content_property: str | None = Field(
        default=None,
        description="Property name to use as main content (e.g., 'body', 'description'). If not specified, all properties are JSON-serialized as content.",
    )
    metadata_properties: list[str] | None = Field(
        default=None,
        description="Properties to include in metadata (e.g., ['title', 'author']). If not specified, all properties are included.",
    )
    filters: WeaviateFilter | None = Field(
        default=None,
        description="Filter applied when searching. Single condition or group with and/or/not.",
    )


class RemoteWeaviateDatasetType(BaseDatasetType):
    """Remote Weaviate dataset type that allows you to query your data
    from a remote Weaviate server.

    It uses the Weaviate vector database to query your data from a remote server.
    """

    NAME = "remote_weaviate"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Weaviate remote dataset type.

        Args:
            config: Configuration dictionary with connection settings
        """
        self.config = RemoteWeaviateConfiguration.model_validate(config)

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
        return "🌐"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this dataset type.

        Returns:
            JSON schema describing configuration requirements
        """
        return RemoteWeaviateConfiguration.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    @classmethod
    async def validate_configuration(cls, configuration: dict[str, Any]) -> None:
        """Validate the configuration for the dataset type.

        Args:
            configuration: Configuration dictionary to validate
        """
        try:
            config = RemoteWeaviateConfiguration.model_validate(configuration)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Validate filters can be built into Weaviate filter objects
        if config.filters and enabled:
            try:
                instance = cls(configuration)
                instance._build_weaviate_filters()
            except Exception as e:
                raise ValueError(f"Invalid filter configuration: {e}") from e

    @property
    def collection_name(self) -> str:
        """Get the name of the collection."""
        return self.config.collection_name

    def _build_weaviate_filters(self) -> Any:
        """Build Weaviate Filter objects from configured filter conditions.

        Returns:
            A Weaviate _Filters object, or None if no filters are configured.
        """
        if not self.config.filters:
            return None

        return self._build_filter_node(self.config.filters, Filter)

    @staticmethod
    def _build_filter_node(node: FilterCondition | FilterGroup, Filter: Any) -> Any:
        """Recursively build a Weaviate filter from a filter node."""
        if isinstance(node, FilterCondition):
            prop_filter = Filter.by_property(node.property)
            method = getattr(prop_filter, OPERATOR_MAP[node.op])
            return method(node.value)

        # FilterGroup
        built = [
            RemoteWeaviateDatasetType._build_filter_node(op, Filter)
            for op in node.operands
        ]

        if node.op == LogicalOperator.AND:
            return Filter.all_of(built)
        elif node.op == LogicalOperator.OR:
            return Filter.any_of(built)
        else:  # NOT
            inner = Filter.all_of(built) if len(built) > 1 else built[0]
            return Filter.not_(inner)

    async def search(
        self, ctx: SearchContext, query: str, params: SearchParameters | None = None
    ) -> SearchResult:
        """Search the dataset for the given query.

        Args:
            ctx: Search context with dataset identifier
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
            # Get the collection
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
                # Content: use specified property OR JSON dump all properties
                if self.config.content_property:
                    content = str(
                        result.properties.get(self.config.content_property, "")
                    )
                else:
                    content = json.dumps(result.properties, default=str)

                # Metadata: use specified properties OR include all properties
                if self.config.metadata_properties is not None:
                    custom_metadata = {
                        k: v
                        for k, v in result.properties.items()
                        if k in self.config.metadata_properties
                    }
                else:
                    custom_metadata = dict(result.properties)

                # Include Weaviate system metadata
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

    @classmethod
    def enabled(cls) -> bool:
        """Check if this dataset type is enabled.

        Returns:
            True if weaviate is installed
        """
        return enabled

    @classmethod
    def connection_fields(cls) -> list[str]:
        """Return list of connection-related configuration fields.

        These fields are shared across all datasets of this type.
        - http_url, grpc_url: Server connection settings
        - api_key: API key for the Weaviate server
        - collection_name: Name of the Weaviate collection
        """
        return ["http_url", "grpc_url", "api_key", "collection_name"]

    async def healthcheck(self) -> HealthcheckResponse:
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
