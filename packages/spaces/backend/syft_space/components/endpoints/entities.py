"""Endpoint database entities."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import JSON, Index, UniqueConstraint
from sqlmodel import Column, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from components.datasets.entities import Dataset
    from components.models.entities import Model
    from components.policies.entities import Policy
    from components.tenants.entities import Tenant


class ResponseType(str, Enum):
    """Type of response for an endpoint."""

    RAW = "raw"  # Only dataset search results
    SUMMARY = "summary"  # Only model chat results (dataset optional, as RAG grounding)
    BOTH = "both"  # Both dataset search + model chat


def validate_response_type_attachments(
    response_type: ResponseType, *, has_dataset: bool, has_model: bool
) -> str | None:
    """Return an error message when the attachments can't serve the response type.

    ``raw`` needs a dataset, ``summary`` needs a model (dataset optional, as
    RAG grounding), ``both`` needs both. Enforced at endpoint creation only;
    pre-existing endpoints keep their legacy query behavior.
    """
    if response_type is ResponseType.RAW and not has_dataset:
        return "response_type 'raw' requires a dataset_id"
    if response_type is ResponseType.SUMMARY and not has_model:
        return "response_type 'summary' requires a model_id"
    if response_type is ResponseType.BOTH and not (has_dataset and has_model):
        return "response_type 'both' requires both a dataset_id and a model_id"
    return None


class Endpoint(SQLModel, table=True):
    """Endpoint entity representing a configured endpoint instance."""

    __tablename__ = "endpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_endpoint_tenant_slug"),
        Index("idx_endpoint_tenant_slug", "tenant_id", "slug"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    name: str = Field(..., description="Name of the endpoint")
    slug: str = Field(..., description="URL slug (unique per tenant)")
    description: str = Field(default="", description="Markdown description")
    summary: str = Field(default="", description="Brief summary")
    dataset_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("datasets.id", ondelete="CASCADE")),
        description="ID of linked dataset (optional)",
    )
    model_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("models.id", ondelete="CASCADE")),
        description="ID of linked model (optional)",
    )
    response_type: str = Field(
        default=ResponseType.BOTH.value,
        description="Type of response (raw/summary/both)",
    )
    published: bool = Field(default=False, description="Whether endpoint is published")
    archived: bool = Field(
        default=False,
        description="Whether endpoint is archived (no new purchases, still queryable)",
    )
    tags: str = Field(default="", description="Comma-separated tags")
    system_prompt: str | None = Field(
        default=None,
        description=(
            "Custom system prompt to override the model's default at request time. "
            "When set, it is prepended (or replaces the first system message) on "
            "every chat invocation."
        ),
    )
    published_to: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of marketplace IDs this endpoint is published to",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: "Tenant" = Relationship(back_populates="endpoints")
    dataset: Optional["Dataset"] = Relationship(
        back_populates="endpoints",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.dataset_id]"},
    )
    model: Optional["Model"] = Relationship(
        back_populates="endpoints",
        sa_relationship_kwargs={"foreign_keys": "[Endpoint.model_id]"},
    )
    policies: list["Policy"] = Relationship(
        back_populates="endpoint",
        sa_relationship_kwargs={"foreign_keys": "[Policy.endpoint_id]"},
    )

    @field_validator("response_type")
    @classmethod
    def validate_response_type(cls, v: str) -> str:
        """Validate response type is valid."""
        if v not in [rt.value for rt in ResponseType]:
            raise ValueError(
                f"response_type must be one of {[rt.value for rt in ResponseType]}"
            )
        return v

    def model_post_init(self, __context: any) -> None:
        """Validate at least one of dataset_id or model_id is provided."""
        if self.dataset_id is None and self.model_id is None:
            raise ValueError("At least one of dataset_id or model_id must be provided")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Legal Q&A Endpoint",
                "slug": "legal-qa",
                "description": "# Legal Q&A\\nAnswers questions about legal documents",
                "summary": "Legal document Q&A system",
                "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
                "model_id": "223e4567-e89b-12d3-a456-426614174000",
                "response_type": "both",
                "published": True,
                "tags": "legal,qa,documents",
            }
        }


class EndpointQualityCard(SQLModel, table=True):
    """What a benchmark said about one endpoint, on one run.

    A table of its own rather than columns on ``endpoints``, and a row per run
    rather than a row per endpoint. Both follow from the same thing: a share is
    unreadable alone. "0.71 accuracy" says almost nothing; "0.71, and 0.78 a
    month ago, on twice the questions" is what an owner actually decides on.
    Overwriting in place answered only the first and discarded the rest.

    Kept locally and not merely forwarded to the marketplaces: the Space needs
    something to show its owner, something to re-send once a marketplace that
    was down comes back, and something to retract.

    Split in two deliberately. The columns are what a list of endpoints needs
    to paint a badge without opening a document per row; ``report`` holds the
    whole card for the detail view.
    """

    __tablename__ = "endpoint_quality_cards"
    __table_args__ = (
        # Every read is "the newest card for this endpoint", or "this
        # endpoint's cards, newest first". One index serves both.
        Index("idx_quality_card_endpoint_checked", "endpoint_id", "checked_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    tenant_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("tenants.id", ondelete="CASCADE")),
        description="Tenant ID for multi-tenancy isolation",
    )
    endpoint_id: UUID = Field(
        ...,
        sa_column=Column(ForeignKey("endpoints.id", ondelete="CASCADE")),
        description="The endpoint this card is about",
    )

    kind: str = Field(
        ...,
        description=(
            "What kind of product was measured: 'answering' (it writes the "
            "answer) or 'retrieval' (it finds the material and someone else's "
            "model answers). Without it `score` is ambiguous"
        ),
    )
    score: float | None = Field(
        default=None,
        description=(
            "Headline share for that kind: accuracy of the answer, or share of "
            "questions where the search found the right material (0..1). Empty "
            "when the run produced no such figure"
        ),
    )
    fabrication_rate: float | None = Field(
        default=None,
        description=(
            "Share of questions with no answer in the corpus that were "
            "answered anyway (0..1). Reported for both kinds"
        ),
    )
    samples: int = Field(..., description="How many questions this run graded")
    reliable: bool = Field(
        ...,
        description=(
            "Whether the benchmark vouches for these figures. False means show "
            "them greyed out or not at all — reasons are in `report`"
        ),
    )
    checked_at: datetime = Field(
        ..., description="When the benchmark that produced this ran"
    )
    report: dict = Field(
        ...,
        sa_column=Column(JSON, nullable=False),
        description="The whole card as reported, for the detail view and re-sends",
    )

    # When the owner withdrew this card from the marketplaces. The row stays:
    # what was published and then taken back is a fact about this endpoint, and
    # deleting it would make the next card look like the first one. The current
    # card is the newest row with this NULL; no such row means no benchmark has
    # reported, which is not a score of zero.
    retracted_at: datetime | None = Field(
        default=None, description="When the owner withdrew it; empty — it still stands"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
