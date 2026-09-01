"""Satellite registration — where this space names itself to a marketplace.

A satellite is the marketplace's registry row for one origin owned by one
account; its id scopes endpoint sync, publish and token audience to this
space rather than the whole account.

Registering an origin is a get-or-create. Changing origin is a move: a POST
with a new origin would create a *second* satellite, so a rotating tunnel URL
would accumulate one per restart. Nothing here deregisters — deleting a
satellite also deletes its endpoints, and a resync does not bring them back.
"""

from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.shared.syfthub_client import (
    NotFoundError,
    Satellite,
    SatelliteKind,
    SatelliteOriginConflictError,
    SyftHubClient,
    SyftHubError,
)


class SatelliteRegistrar:
    """Keeps a marketplace row's satellite pointed at the local public URL."""

    def __init__(self, marketplace_repository: MarketplaceRepository):
        self.marketplace_repository = marketplace_repository

    async def ensure_with_client(
        self,
        client: SyftHubClient,
        base_url: str | None,
        satellite_id: str | None = None,
        kind: SatelliteKind = SatelliteKind.SPACE,
    ) -> Satellite | None:
        """Register or move the satellite; return it for the caller to persist.

        None when there is no origin yet: onboarding connects the marketplace
        before the public URL is set, so that is a normal path, not a failure.
        """
        if not base_url:
            return None
        if satellite_id:
            return await self._move(client, satellite_id, base_url, kind)
        return await client.register_satellite(base_url, kind=kind)

    async def ensure(
        self, marketplace: Marketplace, base_url: str | None, tenant_id: UUID
    ) -> str | None:
        """Log in, sync the satellite, persist it; return the id to use.

        Raises as HTTP so the settings routes surface it; background callers
        catch it themselves.
        """
        if not marketplace.email or not marketplace.password:
            return marketplace.satellite_id

        try:
            async with SyftHubClient(str(marketplace.url)) as client:
                await client.login(marketplace.email, marketplace.password)
                satellite = await self.ensure_with_client(
                    client, base_url, marketplace.satellite_id
                )
        except SyftHubError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to register this space with the marketplace: "
                f"{e.message}",
            ) from e

        if satellite is None:
            return marketplace.satellite_id

        await self.persist(marketplace, tenant_id, satellite)
        return str(satellite.id)

    async def resolve_id(
        self,
        client: SyftHubClient,
        marketplace: Marketplace,
        base_url: str | None,
        tenant_id: UUID,
    ) -> str | None:
        """Return the satellite id to send, registering if there is none yet.

        Not a move — a known id costs no hub call, which the heartbeat's 30s
        cadence needs. None means no public URL, so the caller skips.
        """
        if marketplace.satellite_id:
            return marketplace.satellite_id
        if not base_url:
            return None

        satellite = await client.register_satellite(base_url)
        await self.persist(marketplace, tenant_id, satellite)
        return str(satellite.id)

    async def forget_id(self, marketplace: Marketplace, tenant_id: UUID) -> None:
        """Drop an id the marketplace no longer knows; the next resolve_id
        registers afresh."""
        logger.warning(
            f"Marketplace {marketplace.name} does not know satellite "
            f"{marketplace.satellite_id} — clearing it for re-registration"
        )
        await self.marketplace_repository.set_satellite(marketplace.id, tenant_id, None)
        marketplace.satellite_id = None

    async def persist(
        self, marketplace: Marketplace, tenant_id: UUID, satellite: Satellite
    ) -> None:
        """Store the satellite id on the marketplace row."""
        await self.marketplace_repository.set_satellite(
            marketplace.id, tenant_id, str(satellite.id)
        )
        marketplace.satellite_id = str(satellite.id)

    async def _move(
        self,
        client: SyftHubClient,
        satellite_id: str,
        base_url: str,
        kind: SatelliteKind,
    ) -> Satellite | None:
        """Move the satellite to the current origin, keeping its id.

        A stale id (404) re-registers. A sibling already on the origin (409)
        does not: taking it would drag our endpoints onto their satellite.
        """
        try:
            return await client.move_satellite(satellite_id, base_url)
        except NotFoundError:
            logger.warning(
                f"Satellite {satellite_id} is no longer on this account — "
                f"re-registering {base_url}"
            )
            return await client.register_satellite(base_url, kind=kind)
        except SatelliteOriginConflictError:
            logger.error(
                f"Cannot move satellite {satellite_id} to {base_url}: another "
                f"satellite on this account already serves that origin"
            )
            return None
