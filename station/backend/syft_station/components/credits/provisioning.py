"""Wallet attachment lifecycle for provisioned spaces.

The request lifecycle calls in at three points, through the
WalletAttachments Protocol it owns (requests/interfaces.py):

    approve   → choose_wallet    resolve the admin's wallet pick
    provision → grant_for_space  mint the token + wallet facts (currency,
                                 owner, catalog) for the space's Secret
    delete    → revoke_space     kill the space's credits access

Token invariant: the plaintext exists only in memory between minting and
the k8s Secret write — the station stores the sha256 hash. Every
provisioning attempt mints a FRESH token (revoke-then-mint): the previous
plaintext cannot be recovered, and a failed attempt must not leave a live
credential behind.
"""

import json
from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger

from syft_station.components.credits.bundles import PREPAID_BUNDLES
from syft_station.components.credits.entities import SpaceCreditToken
from syft_station.components.credits.interfaces import SecretPatcher, SpaceDirectory
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
        public_url: str,
    ):
        self.wallets = wallets
        self.credit_tokens = credit_tokens
        self.credits_url = credits_url
        # The station's own public host, minted into spaces as the buyer URL.
        # Always the station's address (where checkout lives) — never the
        # spaces' parent domain, which differs when spaces use a subdomain
        # prefix. Injected from the chart's ingress host (config.public_url).
        self.public_url = public_url

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
        # The station's catalog is the source of truth for bundle pricing —
        # inject it so the space publishes exactly what a purchase will cost.
        bundles = PREPAID_BUNDLES.get(wallet.currency, [])
        return CreditsGrant(
            url=self.credits_url,
            token=plaintext,
            currency=wallet.currency,
            wallet_id=str(wallet.id),
            public_url=self.public_url,
            wallet_owner=(
                str(wallet.hub_user_id) if wallet.hub_user_id is not None else ""
            ),
            bundles=json.dumps(bundles) if bundles else "",
        )

    async def revoke_space(self, space_id: UUID) -> None:
        """Kill the space's credits access (delete/purge)."""
        revoked = await self.credit_tokens.revoke_for_space(space_id)
        if revoked:
            logger.info(f"Revoked {revoked} credits token(s) for space {space_id}")


class WalletRollout:
    """Attach a newly configured wallet to spaces that predate it.

    Runs after the admin creates (or replaces) the wallet: every space that
    is neither attached nor opted out gets a token minted, its Secret
    patched with the credits keys, and an automatic restart so the wallet
    takes effect immediately. A space whose restart fails is flagged
    restart_required — never silently left running on the old env.
    """

    def __init__(
        self,
        spaces: SpaceDirectory,
        provisioner: SecretPatcher,
        credits: SpaceCreditsService,
    ):
        self.spaces = spaces
        self.provisioner = provisioner
        self.credits = credits

    async def attach_unbound_spaces(self, wallet_id: UUID) -> tuple[int, int]:
        """Returns (attached, failed). Failures are logged per space and
        never abort the sweep — the admin re-runs by saving the wallet again."""
        attached = failed = 0
        for space in await self.spaces.get_all():
            if space.wallet_id is not None or space.wallet_opt_out:
                continue
            try:
                grant = await self.credits.grant_for_space(space.id, wallet_id)
                if grant is None:  # wallet vanished mid-sweep
                    break
                data = {
                    "SYFT_CLUSTER_CREDITS_URL": grant.url,
                    "SYFT_CLUSTER_CREDITS_TOKEN": grant.token,
                    "SYFT_CLUSTER_CREDITS_CURRENCY": grant.currency,
                    "SYFT_CLUSTER_CREDITS_WALLET_ID": grant.wallet_id,
                    "SYFT_CLUSTER_PUBLIC_URL": grant.public_url,
                }
                # Optional keys are omitted rather than sent empty — the
                # space parses them as int/JSON, and "" would crash it.
                if grant.wallet_owner:
                    data["SYFT_CLUSTER_WALLET_OWNER"] = grant.wallet_owner
                if grant.bundles:
                    data["SYFT_CLUSTER_BUNDLES"] = grant.bundles
                await self.provisioner.update_space_secret(space.subdomain, data)
                space.wallet_id = wallet_id
                # The pod reads its Secret at start — restart so the wallet
                # takes effect now. A restart failure still counts as
                # attached (the Secret is in place); the flag tells the UI.
                try:
                    await self.provisioner.restart(space.subdomain)
                    space.restart_required = False
                except Exception:
                    logger.exception(f"Auto-restart failed for '{space.subdomain}'")
                    space.restart_required = True
                await self.spaces.update(space)
                attached += 1
            except Exception:
                logger.exception(f"Wallet attach failed for space '{space.subdomain}'")
                failed += 1
        if attached or failed:
            logger.info(f"Wallet rollout: attached {attached}, failed {failed}")
        return attached, failed
