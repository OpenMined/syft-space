"""Auth API routes."""

from fastapi import APIRouter, Depends, Response

from syft_station.components.auth.handlers import AuthHandler
from syft_station.components.auth.schemas import (
    LoginRequest,
    LogoutResponse,
    MeResponse,
)
from syft_station.components.auth.session import (
    SessionUser,
    clear_session_cookie,
    get_current_user,
    set_session_cookie,
)


def build_auth_routes(handler: AuthHandler) -> APIRouter:
    """Build the auth routes."""
    router = APIRouter(prefix="/auth", tags=["auth"])

    def get_handler() -> AuthHandler:
        return handler

    @router.post("/login", response_model=MeResponse)
    async def login(
        request: LoginRequest,
        response: Response,
        handler: AuthHandler = Depends(get_handler),
    ) -> MeResponse:
        """Sign in with SyftHub credentials; sets the session cookie."""
        user = await handler.login(request.email, request.password)
        set_session_cookie(response, user)
        return MeResponse(**user.model_dump())

    @router.post("/logout", response_model=LogoutResponse)
    async def logout(response: Response) -> LogoutResponse:
        clear_session_cookie(response)
        return LogoutResponse()

    @router.get("/me", response_model=MeResponse)
    async def me(user: SessionUser = Depends(get_current_user)) -> MeResponse:
        return MeResponse(**user.model_dump())

    return router
