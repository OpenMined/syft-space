"""Space request API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from syft_station.components.auth.session import (
    SessionUser,
    get_current_user,
    require_admin,
)
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    RejectRequestBody,
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

    @router.post("/{request_id}/approve", response_model=RequestResponse)
    async def approve_request(
        request_id: UUID,
        body: ApproveRequestBody,
        user: SessionUser = Depends(require_admin),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Approve (admin): starts provisioning; 409 on subdomain conflict."""
        return await handler.approve(request_id, body)

    @router.post("/{request_id}/reject", response_model=RequestResponse)
    async def reject_request(
        request_id: UUID,
        body: RejectRequestBody,
        user: SessionUser = Depends(require_admin),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        return await handler.reject(request_id, body.reason)

    @router.post("/{request_id}/retry", response_model=RequestResponse)
    async def retry_request(
        request_id: UUID,
        user: SessionUser = Depends(require_admin),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Retry a FAILED request (admin)."""
        return await handler.retry(request_id)

    @router.post("/{request_id}/delete", response_model=RequestResponse)
    async def delete_space(
        request_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Tear down an active/failed space (owner or admin); marks DELETED."""
        return await handler.delete_space(request_id, user)

    @router.post("/{request_id}/withdraw", response_model=RequestResponse)
    async def withdraw_request(
        request_id: UUID,
        user: SessionUser = Depends(get_current_user),
        handler: RequestHandler = Depends(get_handler),
    ) -> RequestResponse:
        """Withdraw own PENDING request (kept as a state for admin visibility)."""
        return await handler.withdraw(request_id, user)

    return router
