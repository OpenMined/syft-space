"""Spaces API schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

# Derived from the space row, never stored: `attached` = bound to a wallet,
# `declined` = the admin chose "no wallet" at approval, `unattached` = neither
# (usually approved before the station had a wallet).
WalletStatus = Literal["attached", "declined", "unattached"]


class SpaceConditionResponse(BaseModel):
    """One thing about a space that needs an admin action."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    message: str
    created_at: datetime


class SpaceResponse(BaseModel):
    """Built straight off the Space row: conditions arrive with it (the
    relationship is eager) and wallet_status is derived here, so nothing
    assembles this shape by hand."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID | None
    name: str
    subdomain: str
    owner_email: str
    url: str
    version: str
    conditions: list[SpaceConditionResponse] = []
    created_at: datetime

    # Read from the row to derive wallet_status; never serialized.
    wallet_id: UUID | None = Field(default=None, exclude=True)
    wallet_opt_out: bool = Field(default=False, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def wallet_status(self) -> WalletStatus:
        if self.wallet_id is not None:
            return "attached"
        return "declined" if self.wallet_opt_out else "unattached"


class AttachWalletBody(BaseModel):
    """Which wallet to attach. None = the station wallet (v1 has one).

    `reapply` re-runs the attach for a space that is already on the wallet,
    which re-renders its bundle with the wallet's current facts. It is off
    by default because it rotates the space's credits token and restarts
    the pod — never something a stray click should do.
    """

    wallet_id: UUID | None = None
    reapply: bool = False


class AdminUrlResponse(BaseModel):
    """The space URL with the admin API key attached as authToken —
    clicking it opens the space already signed in as its admin."""

    url: str


class SpaceStatusResponse(BaseModel):
    """Live runtime status of a space (read from Kubernetes, never stored)."""

    status: str


class SpaceLogsResponse(BaseModel):
    """A snapshot of the space container's recent log lines (newest last).

    Empty when the space has no running pod (paused or not yet up).
    """

    lines: list[str]


class SpaceUpdateResult(BaseModel):
    """One space's outcome in an update sweep."""

    space_id: UUID
    name: str
    outcome: Literal["updated", "skipped", "failed"]
    detail: str = ""


class UpdateAllResponse(BaseModel):
    supported_version: str
    results: list[SpaceUpdateResult]
