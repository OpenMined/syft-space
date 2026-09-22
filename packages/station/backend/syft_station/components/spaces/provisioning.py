"""Converge a space onto the substrate at the station's supported version.

The one shared "make it so" path: first provisioning, retry after failure,
and update-to-a-new-version all render the same bundle and apply it — the
provisioner is convergent (create-or-patch, PVC kept), so the caller only
decides *when* to converge, never *how*.

Every converge mints a FRESH credits token and admin key Secret — the pod
that comes up always starts with credentials the station currently honors.
"""

from loguru import logger

from syft_station.components.provision.interfaces import Provisioner, SpaceSpec
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.spaces.entities import CLEARED_BY_CONVERGE, Space
from syft_station.components.spaces.interfaces import CreditsService
from syft_station.components.spaces.repository import SpaceRepository


class SpaceConverger:
    """Renders + applies a space's bundle and records the outcome."""

    def __init__(
        self,
        space_repository: SpaceRepository,
        setup_repository: SetupRepository,
        provisioner: Provisioner,
        credits: CreditsService,
    ):
        self.space_repository = space_repository
        self.setup_repository = setup_repository
        self.provisioner = provisioner
        self.credits = credits

    async def converge(self, space: Space, version: str | None = None) -> str:
        """Provision the space at `version`; returns its URL.

        `version` defaults to the station's supported version — attaching a
        wallet passes the space's current one so it re-renders the bundle
        without also rolling the image forward.

        Raises ProvisionError (or any substrate error) on failure — the
        caller decides what that means for its own state. On success the
        space row records the new url/version and the conditions a
        converge resolves are cleared (the pod just started fresh).
        """
        config = await self.setup_repository.get_config()
        target_version = version or config.supported_version
        token_row = await self.space_repository.get_token(space.id)

        # Every attempt mints a FRESH credits token (the previous plaintext
        # is unrecoverable by design); a failed attempt leaves no live grant
        # behind that this attempt would still be using.
        grant = None
        if space.wallet_id:
            grant = await self.credits.grant_for_space(space.id, space.wallet_id)

        spec = SpaceSpec(
            subdomain=space.subdomain,
            space_name=space.name,
            owner_email=space.owner_email,
            version=target_version,
            domain=config.domain,
            admin_token=token_row.token or "" if token_row else "",
            credits_url=grant.url if grant else "",
            credits_token=grant.token if grant else "",
            credits_currency=grant.currency if grant else "",
            credits_wallet_id=grant.wallet_id if grant else "",
            credits_public_url=grant.public_url if grant else "",
            credits_wallet_owner=grant.wallet_owner if grant else "",
            credits_bundles=grant.bundles if grant else "",
        )

        url = await self.provisioner.provision(spec)

        space.url = url
        space.version = target_version
        await self.space_repository.update(space)
        # The pod just started from a freshly rendered bundle, so every
        # condition a converge can resolve is resolved.
        await self.space_repository.clear_conditions(space.id, CLEARED_BY_CONVERGE)
        logger.info(f"Space '{space.subdomain}' converged at {url}")
        return url
