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
    wallet_opt_out: bool = Field(
        default=False,
        description="Admin explicitly declined the wallet at approval. "
        "Distinguishes 'no wallet existed yet' (backfilled when one is "
        "added) from 'keep this space unbilled' (left alone).",
    )
    restart_required: bool = Field(
        default=False,
        description="The space's Secret was patched but the automatic "
        "restart failed — the running pod still has the old env. Cleared "
        "by any successful restart, update, or re-provision.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpaceToken(SQLModel, table=True):
    """The space's admin API key.

    Kept in plaintext: the station mints it into the space's k8s Secret and
    serves it to the owner as an authToken URL (open-the-space link), so
    hiding it here would add no protection. Regenerate replaces it and
    patches the Secret (applies on the space's next restart).

    ``token`` is nullable only for rows from the retired one-time-reveal
    era, whose plaintext was cleared — regenerating heals them.
    """

    __tablename__ = "space_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    space_id: UUID = Field(index=True)
    token: str | None = Field(default=None, description="Plaintext admin API key")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
