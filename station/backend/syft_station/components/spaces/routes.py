"""Spaces API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.spaces.handlers import SpaceHandler
from syft_station.components.spaces.schemas import (
    SpaceResponse,
    SpaceStatusResponse,
    TokenRevealResponse,
    TokenStatusResponse,
)


def build_space_routes(handler: SpaceHandler) -> APIRouter:
    """Build the spaces routes."""
    router = APIRouter(prefix="/spaces", tags=["spaces"])

    def get_handler() -> SpaceHandler:
        return handler

    @router.get("", response_model=list[SpaceResponse])
    async def list_spaces(
        user: SessionUser = Depends(require_admin),
        handler: SpaceHandler = Depends(get_handler),
    ) -> list[SpaceResponse]:
        """All spaces on the station (admin)."""
        return await handler.list_spaces()

    @router.get("/mine", response_model=list[SpaceResponse])
    async def list_mine(
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> list[SpaceResponse]:
        """The signed-in member's spaces."""
        return await handler.list_mine(user.email)

    @router.get("/{space_id}/status", response_model=SpaceStatusResponse)
    async def runtime_status(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> SpaceStatusResponse:
        """Live running/paused/unavailable status, read from Kubernetes."""
        return await handler.runtime_status(space_id, user)

    @router.post("/{space_id}/pause", response_model=SpaceStatusResponse)
    async def pause_space(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> SpaceStatusResponse:
        """Free the space's compute; data is kept (owner or admin)."""
        return await handler.pause(space_id, user)

    @router.post("/{space_id}/resume", response_model=SpaceStatusResponse)
    async def resume_space(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> SpaceStatusResponse:
        """Bring a paused space back online (owner or admin)."""
        return await handler.resume(space_id, user)

    @router.get("/{space_id}/token", response_model=TokenStatusResponse)
    async def token_status(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> TokenStatusResponse:
        """Whether the space admin key has been revealed yet (owner or admin)."""
        return await handler.token_status(space_id, user)

    @router.post("/{space_id}/token/reveal", response_model=TokenRevealResponse)
    async def reveal_token(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> TokenRevealResponse:
        """One-time reveal of the space admin API key (owner or admin)."""
        return await handler.reveal_token(space_id, user)

    @router.post("/{space_id}/token/regenerate", response_model=TokenStatusResponse)
    async def regenerate_token(
        space_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: SpaceHandler = Depends(get_handler),
    ) -> TokenStatusResponse:
        """Replace the space admin API key with a fresh unrevealed one."""
        return await handler.regenerate_token(space_id, user)

    return router
