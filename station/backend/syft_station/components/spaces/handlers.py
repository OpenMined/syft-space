"""Spaces handler — registry reads + admin-token lifecycle."""

from uuid import UUID

from fastapi import HTTPException, status
from loguru import logger

from syft_station.components.auth.session import ROLE_ADMIN, SessionUser
from syft_station.components.provision.interfaces import (
    Provisioner,
    SpaceRuntimeStatus,
)
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.provisioning import SpaceConverger
from syft_station.components.spaces.repository import (
    SpaceRepository,
    generate_space_token,
)
from syft_station.components.spaces.schemas import (
    AdminUrlResponse,
    SpaceResponse,
    SpaceStatusResponse,
    SpaceUpdateResult,
    UpdateAllResponse,
)


class SpaceHandler:
    """Space registry + one-time token reveal / regenerate + runtime ops."""

    def __init__(
        self,
        repository: SpaceRepository,
        provisioner: Provisioner,
        setup_repository: SetupRepository,
        converger: SpaceConverger,
    ):
        self.repository = repository
        self.provisioner = provisioner
        self.setup_repository = setup_repository
        self.converger = converger

    async def list_spaces(self) -> list[SpaceResponse]:
        spaces = await self.repository.get_all()
        return [SpaceResponse.model_validate(s.model_dump()) for s in spaces]

    async def list_mine(self, owner_email: str) -> list[SpaceResponse]:
        spaces = await self.repository.list_by_owner(owner_email)
        return [SpaceResponse.model_validate(s.model_dump()) for s in spaces]

    async def _get_owned_space(self, space_id: UUID, user: SessionUser) -> Space:
        space = await self.repository.get_by_id(space_id)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        if user.role != ROLE_ADMIN and space.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your space",
            )
        return space

    # --- Runtime ops (state lives in Kubernetes, never stored) ---

    async def runtime_status(
        self, space_id: UUID, user: SessionUser
    ) -> SpaceStatusResponse:
        space = await self._get_owned_space(space_id, user)
        try:
            status_ = await self.provisioner.get_status(space.subdomain)
        except Exception as e:
            logger.exception(f"Status read failed for '{space.subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not read the space status",
            ) from e
        return SpaceStatusResponse(status=str(status_))

    async def pause(self, space_id: UUID, user: SessionUser) -> SpaceStatusResponse:
        """Free the space's compute; its data volume is kept."""
        space = await self._get_owned_space(space_id, user)
        try:
            await self.provisioner.pause(space.subdomain)
        except Exception as e:
            logger.exception(f"Pause failed for '{space.subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not pause the space — please try again",
            ) from e
        return await self.runtime_status(space_id, user)

    async def resume(self, space_id: UUID, user: SessionUser) -> SpaceStatusResponse:
        """Bring a paused space back online."""
        space = await self._get_owned_space(space_id, user)
        try:
            await self.provisioner.resume(space.subdomain)
        except Exception as e:
            logger.exception(f"Resume failed for '{space.subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not resume the space — please try again",
            ) from e
        # The fresh pod starts with the current Secret, so any pending
        # Secret patch is applied by coming back up.
        await self._clear_restart_flag(space)
        return await self.runtime_status(space_id, user)

    async def restart(self, space_id: UUID, user: SessionUser) -> SpaceStatusResponse:
        """Roll the space's pods so they start with the current Secret."""
        space = await self._get_owned_space(space_id, user)
        try:
            await self.provisioner.restart(space.subdomain)
        except Exception as e:
            logger.exception(f"Restart failed for '{space.subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not restart the space — please try again",
            ) from e
        await self._clear_restart_flag(space)
        return await self.runtime_status(space_id, user)

    async def update_space(self, space_id: UUID) -> SpaceResponse:
        """Redeploy the space at the station's supported version (admin).

        Same convergent path as provisioning — fresh tokens, data volume
        untouched. Paused spaces are refused: applying the bundle would
        start them.
        """
        space = await self.repository.get_by_id(space_id)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        outcome = await self._update_one(space)
        if outcome.outcome == "skipped":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The space is paused — resume it before updating",
            )
        if outcome.outcome == "failed":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Update failed: {outcome.detail}",
            )
        return SpaceResponse.model_validate(space.model_dump())

    async def update_all(self) -> UpdateAllResponse:
        """Redeploy every outdated space, one at a time (admin).

        Sequential on purpose — one long image pull shouldn't fan out into
        every space restarting at once. Failures never abort the sweep;
        each space reports its own outcome.
        """
        config = await self.setup_repository.get_config()
        results = []
        for space in await self.repository.get_all():
            if space.version == config.supported_version:
                continue
            results.append(await self._update_one(space))
        return UpdateAllResponse(
            supported_version=config.supported_version, results=results
        )

    async def _update_one(self, space: Space) -> SpaceUpdateResult:
        """Converge one space; paused → skipped, errors → failed."""
        try:
            status_ = await self.provisioner.get_status(space.subdomain)
            if status_ == SpaceRuntimeStatus.PAUSED:
                return SpaceUpdateResult(
                    space_id=space.id,
                    name=space.name,
                    outcome="skipped",
                    detail="paused — resume the space first",
                )
            await self.converger.converge(space)
        except Exception as e:
            logger.exception(f"Update failed for '{space.subdomain}'")
            return SpaceUpdateResult(
                space_id=space.id, name=space.name, outcome="failed", detail=str(e)
            )
        return SpaceUpdateResult(space_id=space.id, name=space.name, outcome="updated")

    async def _clear_restart_flag(self, space: Space) -> None:
        if space.restart_required:
            space.restart_required = False
            await self.repository.update(space)

    async def admin_url(self, space_id: UUID, user: SessionUser) -> AdminUrlResponse:
        """The space URL with the admin key as authToken (owner or admin).

        Repeatable by design: the station holds the key anyway (it minted it
        into the space's Secret), so a one-time reveal added no protection.
        """
        space = await self._get_owned_space(space_id, user)
        token_row = await self.repository.get_token(space.id)
        if not token_row or not token_row.token:
            raise HTTPException(status_code=404, detail="No token for this space")
        return AdminUrlResponse(url=self._admin_url(space.url, token_row.token))

    async def regenerate_token(
        self, space_id: UUID, user: SessionUser
    ) -> AdminUrlResponse:
        """Mint a fresh admin key, patch the space's Secret, and restart.

        The pod reads its Secret at start, so the space is restarted to
        apply the new key; if the restart fails the space is flagged
        restart_required instead of silently running on the old key.
        """
        space = await self._get_owned_space(space_id, user)
        fresh = await self.repository.replace_token(space.id, generate_space_token())
        try:
            await self.provisioner.update_space_secret(
                space.subdomain, {"SYFT_ADMIN_API_KEY": fresh.token or ""}
            )
        except Exception as e:
            logger.exception(f"Secret patch failed for '{space.subdomain}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not apply the new key to the space — try again",
            ) from e
        await self._restart_to_apply(space)
        return AdminUrlResponse(url=self._admin_url(space.url, fresh.token or ""))

    async def _restart_to_apply(self, space: Space) -> None:
        """Restart after a Secret patch; flag the space if it fails."""
        flagged = False
        try:
            await self.provisioner.restart(space.subdomain)
        except Exception:
            logger.exception(f"Auto-restart failed for '{space.subdomain}'")
            flagged = True
        if space.restart_required != flagged:
            space.restart_required = flagged
            await self.repository.update(space)

    @staticmethod
    def _admin_url(space_url: str, token: str) -> str:
        """Same shape syft-space itself links with: /frontend/#/?authToken=…"""
        return f"{space_url.rstrip('/')}/frontend/#/?authToken={token}"
