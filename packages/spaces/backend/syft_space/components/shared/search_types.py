"""Search / retrieval pipeline domain types.

``SearchContext`` + ``SearchParameters`` go into
``BaseVectorStore.search``; ``SearchResult`` (a list of
``SearchedDocument``) comes back out.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from syft_space.components.shared.domain_types import Context


class SearchContext(Context):
    """Context for search requests."""

    dataset_id: UUID = Field(..., description="Unique identifier for the dataset")


class SearchParameters(BaseModel):
    """Domain contract for search parameters."""

    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum similarity score, where score = 1 - cosine_distance / 2 "
            "(so 0.5 is cosine similarity 0). Both stores use this mapping."
        ),
    )
    limit: int = Field(
        default=5, ge=1, description="Maximum number of results to return"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in response"
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description="Extra options for the search"
    )


class SearchedDocument(BaseModel):
    """A single document from search results."""

    document_id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="1 - cosine_distance / 2: 1 is identical, 0.5 is orthogonal",
    )


class SearchResult(BaseModel):
    """Domain contract for search results."""

    documents: list[SearchedDocument] = Field(
        default_factory=list, description="List of searched documents"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional search metadata"
    )
