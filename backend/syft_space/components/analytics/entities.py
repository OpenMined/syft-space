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
    """Per-query header. One row per query, regardless of how many
    accounting policies fire.

    Stored in a separate analytics database (analytics.db), detached from
    the main application database. No foreign key constraints — all IDs
    are plain UUIDs for cross-database historical reference.

    Revenue is stored in QueryCostLine (one row per chargeable component)
    so a single query can carry charges across multiple currencies.
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
    query_text: str = Field(
        default="", description="Raw query text submitted by the user"
    )
    status: str = Field(
        default=QueryEventStatus.SUCCESS.value,
        description="Query outcome status",
    )


class QueryCostLine(SQLModel, table=True):
    """One row per chargeable component within a query.

    `tenant_id`, `timestamp`, `user_email`, and `status` are denormalized
    from the parent QueryEvent so per-currency revenue aggregations can
    filter and group purely on this table without joining back to
    query_events.
    """

    __tablename__ = "query_cost_lines"
    __table_args__ = (
        Index(
            "idx_qcl_tenant_ts_currency",
            "tenant_id",
            "timestamp",
            "currency",
        ),
        Index("idx_qcl_event", "query_event_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    query_event_id: UUID = Field(
        ...,
        description="References QueryEvent.id (no FK constraint)",
    )
    tenant_id: UUID = Field(..., description="Tenant (denormalized for aggregation)")
    timestamp: datetime = Field(
        ..., description="Parent event timestamp (denormalized for time-bucket queries)"
    )
    user_email: str = Field(
        ..., description="Querying user (denormalized for top-users)"
    )
    endpoint_id: UUID | None = Field(
        default=None,
        description="Endpoint ID (denormalized for filter)",
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Dataset ID (denormalized for filter)",
    )
    status: str = Field(
        ..., description="Parent event status (denormalized for filter)"
    )
    component: str = Field(
        ...,
        description='Which response component was charged: "summary" or "references"',
    )
    amount: float = Field(..., description="Charged amount in `currency`")
    currency: str = Field(..., description="ISO currency code (e.g., 'USD', 'IDR')")
