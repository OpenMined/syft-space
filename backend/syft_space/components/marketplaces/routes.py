"""Marketplace API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from syft_space.components.marketplaces.handlers import MarketplaceHandler
from syft_space.components.marketplaces.schemas import (
    ConnectMarketplaceRequest,
    EmailVerificationRequiredResponse,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
    ResendMarketplaceOTPRequest,
    VerifyMarketplaceOTPRequest,
)
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_marketplace_routes(handler: MarketplaceHandler) -> APIRouter:
    """Build the marketplace routes.

    Args:
        handler: Marketplace handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/marketplaces", tags=["marketplaces"])

    def get_handler() -> MarketplaceHandler:
        """Dependency to get the marketplace handler."""
        return handler

    @router.post(
        "/register",
        response_model=MarketplaceResponse,
        status_code=201,
        responses={
            202: {
                "model": EmailVerificationRequiredResponse,
                "description": (
                    "Account created on SyftHub but email verification is "
                    "required. Submit the OTP via /marketplaces/verify-otp."
                ),
            },
        },
    )
    async def register_marketplace(
        request: RegisterMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> Response:
        """Register a new marketplace by creating a new SyftHub account.

        On success returns 201 with the persisted marketplace. When SyftHub
        requires OTP verification (SMTP is configured), returns 202 with an
        ``EmailVerificationRequiredResponse`` so the client can prompt for the
        emailed code and POST it to /marketplaces/verify-otp.
        """
        result = await handler.register_marketplace(request, tenant)
        if isinstance(result, EmailVerificationRequiredResponse):
            return JSONResponse(status_code=202, content=result.model_dump(mode="json"))
        return JSONResponse(status_code=201, content=result.model_dump(mode="json"))

    @router.post(
        "/verify-otp",
        response_model=MarketplaceResponse,
        status_code=201,
        responses={
            400: {"description": "Invalid or expired OTP code"},
            404: {"description": "No pending verification for this email"},
        },
    )
    async def verify_marketplace_otp(
        request: VerifyMarketplaceOTPRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Complete a pending marketplace registration with an emailed OTP code.

        Used after ``/register`` returns 202 with ``EMAIL_VERIFICATION_REQUIRED``.
        """
        return await handler.verify_marketplace_otp(request, tenant)

    @router.post("/resend-otp", status_code=200)
    async def resend_marketplace_otp(
        request: ResendMarketplaceOTPRequest,
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> dict:
        """Resend a registration OTP code to the given email."""
        return await handler.resend_marketplace_otp(request)

    @router.post("/connect", response_model=MarketplaceResponse, status_code=201)
    async def connect_marketplace(
        request: ConnectMarketplaceRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Connect to an existing SyftHub account and add as marketplace.

        Args:
            request: Connection request with existing SyftHub credentials
            tenant: Current tenant (injected)

        Returns:
            Created marketplace details
        """
        return await handler.connect_marketplace(request, tenant)

    @router.get("/check-username/{username}", response_model=bool)
    async def check_username_availability(
        username: str,
        handler: MarketplaceHandler = Depends(get_handler),
        url: str | None = None,
    ) -> bool:
        """Check if a username is available.
        Args:
            username: Username to check
            handler: Marketplace handler instance
            url: URL of the Marketplace
        Returns:
            True if username is available, False otherwise.
        """
        return await handler.check_username_availability(url, username)

    @router.get("/", response_model=list[MarketplaceListItem])
    async def list_marketplaces(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> list[MarketplaceListItem]:
        """List all registered marketplaces.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of marketplaces with summary information
        """
        return await handler.list_marketplaces(tenant)

    @router.get("/{id}", response_model=MarketplaceResponse)
    async def get_marketplace(
        id: UUID,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: MarketplaceHandler = Depends(get_handler),
    ) -> MarketplaceResponse:
        """Get details of a specific marketplace.

        Args:
            id: Marketplace ID
            tenant: Current tenant (injected)

        Returns:
            Marketplace details (password not included)
        """
        return await handler.get_marketplace(id, tenant)

    return router
