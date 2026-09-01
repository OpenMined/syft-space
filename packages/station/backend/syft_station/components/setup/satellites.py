"""The station's own satellite on SyftHub.

Registration normally happens as a side effect of health reporting, and
nothing reports health for the station's origin — so unlike a space, the
station has to claim its origin by hand. The publish and mint gates ask
whether the wallet owner's account holds a satellite at the exact credits
origin, which for a managed wallet is this station's host.

The id is a station-level fact, like the token that registers it: wallets
added later share both.
"""

from loguru import logger

from syft_station.components.auth.syfthub import (
    SyftHubIdentityClient,
    SyftHubSatelliteError,
)
from syft_station.components.setup.repository import SetupRepository


class StationSatelliteRegistrar:
    """Keeps the station registered at its current public origin."""

    def __init__(
        self,
        repository: SetupRepository,
        hub: SyftHubIdentityClient,
        public_url: str,
        seed_satellite_id: str = "",
    ):
        self.repository = repository
        self.hub = hub
        self.public_url = public_url
        # Env seed, applied only to an empty stored value: a re-spun station
        # reclaims its registration rather than making a second one.
        self.seed_satellite_id = seed_satellite_id

    async def ensure(self, pat: str) -> str | None:
        """Register or move the station's satellite; return its id.

        None when there is nothing to register against — no public URL, or
        no token to register with.
        """
        if not self.public_url or not pat:
            return None

        config = await self.repository.get_config()
        satellite_id = config.satellite_id or self.seed_satellite_id

        satellite = None
        if satellite_id:
            satellite = await self.hub.move_satellite(
                pat, satellite_id, self.public_url
            )
        if satellite is None:
            satellite = await self.hub.register_satellite(pat, self.public_url)

        if satellite.id != config.satellite_id:
            await self.repository.update_satellite_id(satellite.id)
        return satellite.id

    async def ensure_quietly(self, pat: str) -> None:
        """Same, but a failure is logged rather than raised.

        Used where registration is a side effect of something else that has
        already succeeded — saving the identity, or booting. Minting only
        breaks once the hub enforces the origin check, and the next boot
        retries, so this must not fail the caller.
        """
        try:
            satellite_id = await self.ensure(pat)
        except SyftHubSatelliteError as e:
            logger.error(f"SyftHub refused this station's satellite: {e}")
        except Exception as e:
            logger.warning(f"Could not register this station's satellite: {e}")
        else:
            if satellite_id:
                logger.info(
                    f"Station registered as satellite {satellite_id} "
                    f"at {self.public_url}"
                )
