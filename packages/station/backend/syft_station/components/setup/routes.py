"""Setup API routes."""

from fastapi import APIRouter, Depends

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.setup.handlers import (
    SetupHandler,
    StationIdentityHandler,
)
from syft_station.components.setup.schemas import (
    ConnectIdentityRequest,
    IdentityResponse,
    SetupResponse,
    UpdateSetupRequest,
)


def build_setup_routes(
    handler: SetupHandler, identity_handler: StationIdentityHandler
) -> APIRouter:
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

    @router.get("/identity", response_model=IdentityResponse)
    async def get_identity(
        user: SessionUser = Depends(require_admin),
        handler: SetupHandler = Depends(get_handler),
    ) -> IdentityResponse:
        """The station's SyftHub identity — never the token itself (admin)."""
        return await identity_handler.get()

    @router.put("/identity", response_model=IdentityResponse)
    async def connect_identity(
        request: ConnectIdentityRequest,
        user: SessionUser = Depends(require_admin),
        handler: SetupHandler = Depends(get_handler),
    ) -> IdentityResponse:
        """Connect (or rotate) the station's SyftHub identity (admin).

        Registers the station's satellite as a side effect.
        """
        return await identity_handler.connect(request, user.email)

    return router
