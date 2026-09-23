"""Space registry database entities."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel


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
    wallet_opt_out: bool = Field(
        default=False,
        description="Admin explicitly declined the wallet at approval. "
        "Distinguishes 'no wallet existed yet' (backfilled when one is "
        "added) from 'keep this space unbilled' (left alone).",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # selectin: one extra query for the whole result set, so SpaceResponse
    # builds off the row with no assembly.
    conditions: list["SpaceCondition"] = Relationship(
        back_populates="space",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


class SpaceToken(SQLModel, table=True):
    """The space's admin API key.

    Kept in plaintext: the station mints it into the space's k8s Secret and
    serves it to the owner as an authToken URL (open-the-space link), so
    hiding it here would add no protection. Regenerate replaces it, patches
    the Secret, and restarts the space to apply it.

    ``token`` is nullable only for rows from the retired one-time-reveal
    era, whose plaintext was cleared — regenerating heals them.
    """

    __tablename__ = "space_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(index=True)
    token: str | None = Field(default=None, description="Plaintext admin API key")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpaceConditionType(StrEnum):
    """The things that can be wrong with a space and need an admin action."""

    RESTART_REQUIRED = "restart_required"
    WALLET_STALE = "wallet_stale"


# A restart does NOT clear WALLET_STALE: the pod comes back reading the same
# Secret, so only re-rendering the bundle resolves it.
CLEARED_BY_RESTART = frozenset({SpaceConditionType.RESTART_REQUIRED})
CLEARED_BY_CONVERGE = frozenset(SpaceConditionType)


class SpaceCondition(SQLModel, table=True):
    """Something about a space that needs an admin action — one row per
    (space, type). Only facts the station knows and cannot re-read belong
    here; see docs/requests-and-spaces.md#space-conditions."""

    __tablename__ = "space_conditions"
    __table_args__ = (Index("idx_space_condition", "space_id", "type", unique=True),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(foreign_key="spaces.id", index=True)
    type: str = Field(description="A SpaceConditionType value")
    message: str = Field(
        description="Shown to the admin. Written when the condition is "
        "raised and frozen — it describes what happened at the time, which "
        "can no longer be derived once the cause has moved on."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    space: Space = Relationship(back_populates="conditions")
