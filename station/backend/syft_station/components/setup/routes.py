"""Setup API routes."""

from fastapi import APIRouter, Depends

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.setup.handlers import SetupHandler
from syft_station.components.setup.schemas import SetupResponse, UpdateSetupRequest


def build_setup_routes(handler: SetupHandler) -> APIRouter:
    """Build the setup routes."""
    router = APIRouter(prefix="/setup", tags=["setup"])

    def get_handler() -> SetupHandler:
        return handler

    @router.get("", response_model=SetupResponse)
    async def get_setup(
        user: SessionUser = Depends(get_current_user),
        handler: SetupHandler = Depends(get_handler),
    ) -> SetupResponse:
        """Current station configuration (any signed-in user)."""
        return await handler.get_setup()

    @router.put("", response_model=SetupResponse)
    async def update_setup(
        request: UpdateSetupRequest,
        user: SessionUser = Depends(require_admin),
        handler: SetupHandler = Depends(get_handler),
    ) -> SetupResponse:
        """Update the station configuration (admin)."""
        return await handler.update_setup(request)

    return router
