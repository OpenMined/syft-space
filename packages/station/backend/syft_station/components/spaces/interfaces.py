"""Seams the spaces component depends on (consumer-owned interfaces).

Converging a space needs a fresh credits grant, but the spaces component
never imports the credits component — it declares the one capability it
needs here, and the credits SpaceCreditsService satisfies it structurally.
"""

from typing import Protocol
from uuid import UUID

from syft_station.components.provision.interfaces import CreditsGrant


class CreditsGranter(Protocol):
    """The one wallet capability converging a space needs."""

    async def grant_for_space(
        self, space_id: UUID, wallet_id: UUID
    ) -> CreditsGrant | None:
        """Mint a fresh credits token for this space (revoking any previous)."""
        ...
