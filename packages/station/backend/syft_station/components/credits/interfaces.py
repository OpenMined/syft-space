"""Seams the credits component depends on (consumer-owned interfaces).

Money views attribute earnings to spaces, and replacing the wallet flags
the spaces carrying its old facts — but the credits component never imports
the spaces component. It declares the minimal shapes it needs here, and the
spaces repository satisfies them structurally.
"""

from typing import Protocol
from uuid import UUID


class SpaceFlags(Protocol):
    """The one registry call the wallet save needs: flag the spaces carrying
    facts this save has just changed."""

    async def flag_wallet_stale(
        self, message: str, wallet_id: UUID | None = None
    ) -> int: ...


class SpaceIdentity(Protocol):
    """Who a space is (or was): the attribution money views render."""

    name: str
    subdomain: str
    owner_email: str
    deleted: bool


class SpaceIdentities(Protocol):
    """Attribution lookup for money views, keyed by space id.

    Deleting a space removes only its registry row — the ledger keeps
    earning in the space's name, so this lookup must also resolve deleted
    spaces (the request rows they were born from are never deleted).
    """

    async def space_identities(self) -> dict[UUID, SpaceIdentity]: ...
