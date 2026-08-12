"""Request database entities.

A ``Request`` is a member ask the admin reviews and resolves. It has a
``type`` (create a space, delete a space, …); the type decides what approval
*does*. This is deliberately separate from the ``spaces`` table: a Space is
the live resource, a Request is a typed action about one — a space's history
is the trail of requests referencing it.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RequestType(StrEnum):
    """What the request asks for. New member actions add a value here."""

    CREATE_SPACE = "create_space"
    DELETE_SPACE = "delete_space"


class RequestStatus(StrEnum):
    """Review lifecycle, generic to every type.

    PENDING → APPROVED is the happy path (approval runs the type's side
    effect). REJECTED (admin declines) and WITHDRAWN (owner cancels their own
    pending ask) are terminal. PROVISIONING and FAILED apply only to
    create_space — the one type whose approval has an async, fallible side
    effect (provisioning); FAILED is admin-retryable.
    """

    PENDING = "pending"
    PROVISIONING = "provisioning"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    FAILED = "failed"


# A create_space request in these states hasn't produced a space yet (or is
# retrying), so it reserves its subdomain and occupies the owner's "one
# pending create" slot. Once APPROVED the space exists — from then on the
# slot is the space itself (unique per owner), not the request. Backstopped
# by the partial unique index uq_owner_open_create; keep the two in sync.
OPEN_CREATE_STATUSES = (
    RequestStatus.PENDING,
    RequestStatus.PROVISIONING,
    RequestStatus.FAILED,
)


class RequestOrigin(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class Request(SQLModel, table=True):
    """A typed member request the admin reviews."""

    __tablename__ = "requests"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    type: str = Field(index=True, description="RequestType discriminator")
    status: str = Field(default=RequestStatus.PENDING.value, index=True)
    owner_email: str = Field(index=True)
    # The space this request targets. NULL for create_space until it's
    # approved (then set to the space it produced).
    space_id: UUID | None = Field(default=None)
    # Requested name/subdomain — create_space only. subdomain is a real column
    # (not payload) so the reservation index can key on it.
    space_name: str | None = Field(default=None)
    subdomain: str | None = Field(default=None, index=True)
    reason: str = Field(default="", description="Owner's note on the ask")
    resolution_note: str | None = Field(
        default=None, description="Admin's note when approving/rejecting"
    )
    # Type-specific fields future request types need (rename's new_name, …).
    # create/delete need none, so it stays empty for them.
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    origin: str = Field(default=RequestOrigin.MEMBER.value)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = Field(default=None)
