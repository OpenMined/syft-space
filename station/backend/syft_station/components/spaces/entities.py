"""Space registry database entities."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Space(SQLModel, table=True):
    """A provisioned member space.

    Runtime status is deliberately NOT a column — Kubernetes is the source
    of truth for whether the space is running (read live in C2).
    """

    __tablename__ = "spaces"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    request_id: UUID | None = Field(
        default=None, description="The request this space was approved from"
    )
    name: str = Field(description="Display name")
    subdomain: str = Field(index=True, description="DNS-1123 slug; unique per station")
    owner_email: str = Field(index=True)
    url: str = Field(default="", description="Public URL once provisioned")
    version: str = Field(default="", description="syft-space version deployed")
    wallet_id: UUID | None = Field(
        default=None,
        description="Station wallet this space is attached to (the admin's "
        "pick at approval; None = no managed credits). The minted "
        "SpaceCreditToken rows are the materialized binding.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpaceToken(SQLModel, table=True):
    """The space's admin API key, held for a one-time reveal to the owner.

    Plaintext is kept only until the owner reveals it, then cleared. The
    provisioner injects the token into the space's Secret at creation, so
    the station never needs it again after reveal.
    """

    __tablename__ = "space_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(index=True)
    token: str | None = Field(
        default=None, description="Plaintext, cleared after first reveal"
    )
    revealed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
