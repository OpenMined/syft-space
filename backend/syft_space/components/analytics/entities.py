"""Analytics entities for query event logging."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, Index, SQLModel


class QueryEventStatus(str, Enum):
    """Status of a query event."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    NOT_PUBLISHED = "not_published"
    PAYMENT_REQUIRED = "payment_required"
    POLICY_VIOLATION = "policy_violation"
    INTERNAL_ERROR = "internal_error"


class QueryEvent(SQLModel, table=True):
    """Persistent record of a query processed by the system.

    Stored in a separate analytics database (analytics.db), detached from
    the main application database. No foreign key constraints — all IDs
    are plain UUIDs for cross-database historical reference.
    """

    __tablename__ = "query_events"
    __table_args__ = (
        Index("idx_qe_tenant_timestamp", "tenant_id", "timestamp"),
        Index("idx_qe_tenant_endpoint", "tenant_id", "endpoint_id"),
        Index("idx_qe_tenant_user", "tenant_id", "user_email"),
        Index("idx_qe_tenant_dataset", "tenant_id", "dataset_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the query was processed (UTC)",
    )
    tenant_id: UUID = Field(..., description="Tenant that owns the queried endpoint")
    endpoint_id: UUID | None = Field(
        default=None, description="Endpoint ID (None if endpoint not found)"
    )
    endpoint_slug: str = Field(
        ..., description="Human-readable endpoint identifier (denormalized)"
    )
    dataset_id: UUID | None = Field(
        default=None, description="Dataset ID (None if endpoint has no dataset)"
    )
    user_email: str = Field(..., description="Email of the querying user")
    revenue_amount: float = Field(
        default=0.0, description="Amount charged for this query"
    )
    currency: str = Field(default="USD", description="Currency of the revenue amount")
    status: str = Field(
        default=QueryEventStatus.SUCCESS.value,
        description="Query outcome status",
    )
