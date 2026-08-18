"""Configuration schema for the remote Weaviate vector store."""

from pydantic import BaseModel, Field, HttpUrl

from syft_space.components.vector_stores.weaviate_remote.filters import WeaviateFilter

DEFAULT_SIMILARITY_THRESHOLD = 0.5


class RemoteWeaviateVectorStoreConfiguration(BaseModel):
    """Configuration for the remote Weaviate vector store.

    Weaviate is read-only from this process — config covers connection
    + content/metadata mapping + optional query-time filters.
    """

    http_url: HttpUrl = Field(..., description="The HTTP URL of the Weaviate server")
    grpc_url: HttpUrl = Field(..., description="The gRPC URL of the Weaviate server.")
    api_key: str = Field(..., description="The API key for the Weaviate server")
    collection_name: str = Field(..., description="The name of the Weaviate collection")
    headers: dict[str, str] | None = Field(
        default=None,
        description=(
            "Additional HTTP headers for third-party API keys "
            "(e.g., {'X-Cohere-Api-Key': 'key', 'X-OpenAI-Api-Key': 'key'})"
        ),
        json_schema_extra={"secret": True},
    )
    default_similarity_threshold: float = Field(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        description="The default similarity threshold for the Weaviate collection",
    )
    content_property: str | None = Field(
        default=None,
        description=(
            "Property name to use as main content (e.g., 'body', 'description'). "
            "If not specified, all properties are JSON-serialized as content."
        ),
    )
    metadata_properties: list[str] | None = Field(
        default=None,
        description=(
            "Properties to include in metadata (e.g., ['title', 'author']). "
            "If not specified, all properties are included."
        ),
    )
    filters: WeaviateFilter | None = Field(
        default=None,
        description=(
            "Filter applied when searching. Single condition or group with and/or/not."
        ),
    )
