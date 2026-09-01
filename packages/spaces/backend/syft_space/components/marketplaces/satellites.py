"""Satellite registration — the one place this space names itself to a hub.

A satellite is the marketplace's registry row for one origin owned by one
account. Its id scopes endpoint sync, publish and token audience to *this*
space instead of everything the account runs, which is what makes more than
one space per account possible.

Two facts shape the flow below:

- ``POST /satellites`` is a get-or-create, idempotent on the origin *after*
  canonicalisation — so the local URL goes over verbatim and lands on the
  same satellite every time.
- A *changed* origin is a move, never a fresh POST: POST with a new origin
  creates a second satellite, so a rotating tunnel URL would otherwise
  accumulate one per restart. A move to the origin the satellite already has
  is a no-op that returns 200, so the move needs no change detection.

Registration is a durable fact about where this account serves from, and it
outlives any single process: nothing here deregisters on shutdown. Deleting
a satellite would take its endpoints — and their stars, uptime history and
collective memberships — with it, and a resync brings none of that back.
Endpoints deactivate on their own once health reports stop.
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

        Returns None when there is no origin to register — during onboarding
        the marketplace is connected before the public URL is set, so this is
        the normal path there, not a failure.

        Args:
            client: Authenticated client for the marketplace
            base_url: This space's current public URL
            satellite_id: Satellite id already stored, if any
            kind: "space" — this repo never registers a station
        """
        if not base_url:
            return None
        if satellite_id:
            return await self._move(client, satellite_id, base_url, kind)
        return await client.register_satellite(base_url, kind=kind)

    async def ensure(
        self, marketplace: Marketplace, base_url: str | None, tenant_id: UUID
    ) -> str | None:
        """Log in to the marketplace, sync the satellite, persist the result.

        Returns the satellite id to use for subsequent calls. Raises the
        marketplace's error as HTTP so the settings routes surface it —
        background callers catch it themselves.
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

        A stale id (404) is recoverable — re-register and adopt the new id.
        A sibling holding the origin (409) is not: taking it over would drag
        this space's endpoints onto another space's satellite, so the stored
        id is kept and the clash is left for an operator.
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
                f"satellite on this account already serves that origin. "
                f"Two spaces cannot share a public URL."
            )
            return None
