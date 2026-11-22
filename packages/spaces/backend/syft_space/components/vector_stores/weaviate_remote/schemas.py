"""Configuration schema for the remote Weaviate vector store."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

from syft_space.components.shared.config_flags import Visibility, cfg_flags
from syft_space.components.shared.filter_types import FilterNode, FilterValueDtype


class SearchMode(StrEnum):
    """How a query is matched against the collection."""

    VECTOR = "vector"
    HYBRID = "hybrid"


class RemoteWeaviateVectorStoreConfiguration(BaseModel):
    """Configuration for the remote Weaviate vector store.

    Weaviate is read-only from this process — config covers connection
    + content/metadata mapping + optional query-time filters. Connection,
    collection and mapping fields are editable after creation; the
    filters are fixed.
    """

    http_url: HttpUrl = Field(
        ...,
        description="The HTTP URL of the Weaviate server",
        json_schema_extra=cfg_flags(editable=True),
    )
    grpc_url: HttpUrl = Field(
        ...,
        description="The gRPC URL of the Weaviate server.",
        json_schema_extra=cfg_flags(editable=True),
    )
    api_key: str = Field(
        ...,
        description="The API key for the Weaviate server",
        json_schema_extra=cfg_flags(editable=True, visibility=Visibility.SECRET),
    )
    collection_name: str = Field(
        ...,
        description="The name of the Weaviate collection",
        json_schema_extra=cfg_flags(editable=True),
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description=(
            "Additional HTTP headers for third-party API keys "
            "(e.g., {'X-Cohere-Api-Key': 'key', 'X-OpenAI-Api-Key': 'key'})"
        ),
        json_schema_extra=cfg_flags(editable=True, visibility=Visibility.SECRET),
    )
    content_property: str | None = Field(
        default=None,
        description=(
            "Property name to use as main content (e.g., 'body', 'description'). "
            "If not specified, all properties are JSON-serialized as content."
        ),
        json_schema_extra=cfg_flags(editable=True),
    )
    metadata_properties: list[str] | None = Field(
        default=None,
        description=(
            "Properties returned as document metadata and declared on the "
            "endpoint (e.g., ['title', 'author']). If not specified, no "
            "property is returned; only creation_time is."
        ),
        json_schema_extra=cfg_flags(editable=True),
    )
    search_mode: SearchMode = Field(
        default=SearchMode.VECTOR,
        description=(
            "How a query is matched: 'vector' is nearest-neighbour only; "
            "'hybrid' fuses it with a keyword (BM25) search over every "
            "searchable text property."
        ),
        json_schema_extra=cfg_flags(editable=True),
    )
    alpha: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Hybrid mode only: weight of the vector leg. 1.0 is vector only, "
            "0.0 is keywords only."
        ),
        json_schema_extra=cfg_flags(editable=True),
    )
    filters: FilterNode | None = Field(
        default=None,
        description=(
            "Filter applied when searching. Single condition or group with and/or/not."
        ),
    )

    @field_validator("filters", mode="before")
    @classmethod
    def _default_dtype(cls, node: Any) -> Any:
        """An owner's condition without a dtype is coerced as a string, as
        the form always did; a query's condition carries none on purpose."""
        if isinstance(node, dict):
            if node.get("type", "condition") == "condition":
                return {"value_dtype": FilterValueDtype.STRING.value, **node}
            if isinstance(node.get("operands"), list):
                return {
                    **node,
                    "operands": [cls._default_dtype(o) for o in node["operands"]],
                }
        return node
