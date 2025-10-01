from ast import Dict
from ast import List
from enum import Enum
from pydantic import BaseModel
from pydantic import Field
from pydantic import Optional
from pydantic import Any


class HealthcheckStatus(str, Enum):
    """Status for the data source healthcheck."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthcheckResponse(BaseModel):
    """Response for the data source healthcheck."""

    status: HealthcheckStatus


class SearchParameters(BaseModel):
    """Parameters for the data source search."""

    similarity_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Similarity threshold for matching"
    )
    limit: int = Field(
        default=5, ge=1, description="Maximum number of results to return"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    extra_options: Dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the search"
    )


class SearchedDocument(BaseModel):
    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(
        ..., description="Similarity score for the document"
    )


class SearchResult(BaseModel):
    """Message in the response"""

    documents: List[SearchedDocument] = Field(
        ..., description="List of searched documents"
    )
    cost: float = Field(..., description="Cost of the search")
    search_engine: str = Field(..., description="Search engine used")
    api_version: str = Field(..., description="API version used")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
