"""Seams the spaces component depends on (consumer-owned interfaces).

Attaching a wallet and converging a space both need the credits component,
but the spaces component never imports it — it declares the capabilities it
needs here, and the credits SpaceCreditsService satisfies them structurally.
"""

from typing import Protocol
from uuid import UUID

from syft_station.components.provision.interfaces import CreditsGrant


class CreditsService(Protocol):
    """The wallet capabilities converging and attaching a space need."""

    async def choose_wallet(self, requested_id: UUID | None) -> UUID | None:
        """Resolve a wallet pick; None means the station wallet, if any."""
        ...

    async def grant_for_space(
        self, space_id: UUID, wallet_id: UUID
    ) -> CreditsGrant | None:
        """Mint a fresh credits token for this space (revoking any previous)."""
        ...
