"""Seams the request lifecycle depends on (consumer-owned interfaces).

The handler orchestrates approve → provision → delete and needs a wallet
attachment policy at each step. It owns this Protocol; the credits
component's SpaceCreditsService satisfies it structurally — the requests
component never imports credits code.
"""

from typing import Protocol
from uuid import UUID

from syft_station.components.provision.interfaces import CreditsGrant


class WalletAttachments(Protocol):
    """Wallet attachment lifecycle for provisioned spaces."""

    async def choose_wallet(self, requested_id: UUID | None) -> UUID | None:
        """Resolve the approve-dialog pick; None = station has no wallet."""
        ...

    async def grant_for_space(
        self, space_id: UUID, wallet_id: UUID
    ) -> CreditsGrant | None:
        """Mint a fresh credits token for this space (revoking any previous)."""
        ...

    async def revoke_space(self, space_id: UUID) -> None:
        """Kill the space's credits access (delete/purge)."""
        ...
