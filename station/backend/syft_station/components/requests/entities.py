"""Space request database entities."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class RequestStatus(StrEnum):
    """Space request lifecycle.

    PENDING → PROVISIONING → ACTIVE is the happy path. REJECTED and
    WITHDRAWN are terminal; FAILED is retryable by the admin; DELETED means
    the space was removed (data retained). Only PENDING / PROVISIONING /
    ACTIVE reserve the subdomain.
    """

    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    REJECTED = "rejected"
    FAILED = "failed"
    DELETED = "deleted"
    WITHDRAWN = "withdrawn"


SUBDOMAIN_RESERVING_STATUSES = (
    RequestStatus.PENDING,
    RequestStatus.PROVISIONING,
    RequestStatus.ACTIVE,
)


class RequestOrigin(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class SpaceRequest(SQLModel, table=True):
    """A member's (or admin's) request for a space."""

    __tablename__ = "space_requests"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_name: str = Field(description="Requested display name")
    subdomain: str = Field(index=True, description="Requested DNS-1123 slug")
    owner_email: str = Field(index=True)
    origin: str = Field(default=RequestOrigin.MEMBER.value)
    status: str = Field(default=RequestStatus.PENDING.value, index=True)
    reject_reason: str | None = Field(default=None)
    space_id: UUID | None = Field(
        default=None, description="Set once a space is created at approval"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
