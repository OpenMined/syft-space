"""Wallet attachment lifecycle for provisioned spaces.

The request lifecycle calls in at three points, through the
WalletAttachments Protocol it owns (requests/interfaces.py):

    approve   → choose_wallet    resolve the admin's wallet pick
    provision → grant_for_space  mint the token for the space's Secret
    delete    → revoke_space     kill the space's credits access

Token invariant: the plaintext exists only in memory between minting and
the k8s Secret write — the station stores the sha256 hash. Every
provisioning attempt mints a FRESH token (revoke-then-mint): the previous
plaintext cannot be recovered, and a failed attempt must not leave a live
credential behind.
"""

from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger

from syft_station.components.credits.entities import SpaceCreditToken
from syft_station.components.credits.repository import (
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.tokens import (
    generate_credit_token,
    hash_credit_token,
)
from syft_station.components.provision.interfaces import CreditsGrant


class SpaceCreditsService:
    """Wallet attachment lifecycle for provisioned spaces.

    Satisfies the requests component's WalletAttachments Protocol
    (structurally — no import in either direction).
    """

    def __init__(
        self,
        wallets: WalletRepository,
        credit_tokens: SpaceCreditTokenRepository,
        credits_url: str,
    ):
        self.wallets = wallets
        self.credit_tokens = credit_tokens
        self.credits_url = credits_url

    async def choose_wallet(self, requested_id: UUID | None) -> UUID | None:
        """Resolve the approve-dialog wallet pick.

        None means "the station wallet, if one exists" (the default dropdown
        entry); an explicit id must exist. Returns None when the station has
        no wallet — the space is then provisioned without managed credits.
        """
        if requested_id is not None:
            wallet = await self.wallets.get_by_id(requested_id)
            if wallet is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )
            return wallet.id
        active = await self.wallets.get_active()
        return active.id if active else None

    async def grant_for_space(
        self, space_id: UUID, wallet_id: UUID
    ) -> CreditsGrant | None:
        """Mint a fresh credits token for this space (revoking any previous).

        Returns None — space provisions without credits — if the wallet has
        meanwhile disappeared; the attachment intent stays on the space and
        takes effect on a later re-provision.
        """
        wallet = await self.wallets.get_by_id(wallet_id)
        if wallet is None:
            logger.warning(
                f"Space {space_id} is attached to wallet {wallet_id} which no "
                "longer exists — provisioning without credits"
            )
            return None

        await self.credit_tokens.revoke_for_space(space_id)
        plaintext = generate_credit_token()
        await self.credit_tokens.create(
            SpaceCreditToken(
                space_id=space_id,
                wallet_id=wallet.id,
                token_hash=hash_credit_token(plaintext),
            )
        )
        return CreditsGrant(
            url=self.credits_url, token=plaintext, currency=wallet.currency
        )

    async def revoke_space(self, space_id: UUID) -> None:
        """Kill the space's credits access (delete/purge)."""
        revoked = await self.credit_tokens.revoke_for_space(space_id)
        if revoked:
            logger.info(f"Revoked {revoked} credits token(s) for space {space_id}")
