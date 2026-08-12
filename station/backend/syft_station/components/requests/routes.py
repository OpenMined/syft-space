"""Space request API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
)
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    PatchRequestBody,
    RequestResponse,
    SubmitRequestBody,
)


def build_request_routes(handler: RequestHandler) -> APIRouter:
    """Build the space-request routes."""
    router = APIRouter(prefix="/requests", tags=["requests"])

    def get_handler() -> RequestHandler:
        return handler

    @router.get("", response_model=list[RequestResponse])
    async def list_requests(
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> list[RequestResponse]:
        """Member: own requests. Admin: all requests."""
        return await handler.list_requests(user)

    @router.get("/{request_id}", response_model=RequestResponse)
    async def get_request(
        request_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """One request for status polling; members see only their own."""
        return await handler.get_request(request_id, user)

    @router.post("", response_model=RequestResponse, status_code=201)
    async def submit_request(
        body: SubmitRequestBody,
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Submit a space request (admin submissions get origin=admin)."""
        return await handler.submit(body, user)

    @router.patch("/{request_id}", response_model=RequestResponse)
    async def transition_request(
        request_id: UUID,
        body: PatchRequestBody,
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Drive a request's lifecycle by its target status.

        approved/rejected are admin-only (approve starts provisioning or, for
        a failed create, retries; a delete tears the space down). withdrawn
        is the owner's (or admin's). The handler enforces the roles per
        transition. Admin housekeeping-delete is POST a delete_space request,
        then PATCH it approved.
        """
        return await handler.transition(request_id, body, user)

    return router
