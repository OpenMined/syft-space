"""Marketplace handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.schemas import (
    EMAIL_VERIFICATION_REQUIRED_CODE,
    ConnectMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
    ResendMarketplaceOTPRequest,
    VerifyMarketplaceOTPRequest,
)
from syft_space.components.shared.syfthub_client import (
    SyftHubClient,
    SyftHubError,
    UserResponse,
)
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings


class MarketplaceHandler:
    """Handler for marketplace business logic."""

    def __init__(self, repository: MarketplaceRepository):
        """Initialize the marketplace handler.

        Args:
            repository: Marketplace repository
        """
        self.repository = repository

    async def register_marketplace(
        self, request: RegisterMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse | JSONResponse:
        """Register a new marketplace by creating a new SyftHub account.

        Returns a 201 MarketplaceResponse on success. When SyftHub requires
        email verification, returns a 202 JSON body with code
        ``EMAIL_VERIFICATION_REQUIRED`` so the client can collect the OTP
        and call ``/verify-otp`` to finish setup.
        """
        async with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                register_response = await syfthub_client.register(
                    username=request.username,
                    email=request.email,
                    full_name=request.name,
                    password=request.password,
                )

                if register_response.requires_email_verification:
                    return JSONResponse(
                        status_code=202,
                        content={
                            "code": EMAIL_VERIFICATION_REQUIRED_CODE,
                            "message": (
                                "Account created. Enter the verification code "
                                "sent to your email to finish setup."
                            ),
                            "email": request.email,
                            "url": str(request.url),
                        },
                    )

                await syfthub_client.login(request.email, request.password)
                await self._sync_public_url(syfthub_client)
            except SyftHubError as e:
                raise e.to_http_exception() from e

        return await self._persist_marketplace_after_signup(
            tenant=tenant,
            url=str(request.url),
            user=register_response.user,
            password=request.password,
        )

    async def verify_marketplace_otp(
        self, request: VerifyMarketplaceOTPRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Complete a pending registration by verifying the OTP, then persist."""
        async with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                verify_response = await syfthub_client.verify_otp(
                    email=request.email,
                    code=request.code,
                )
                # /verify-otp already issued tokens — skip the extra login round-trip.
                syfthub_client.authenticate_with_tokens(
                    verify_response.access_token, verify_response.refresh_token
                )
                await self._sync_public_url(syfthub_client)
            except SyftHubError as e:
                raise e.to_http_exception() from e

        return await self._persist_marketplace_after_signup(
            tenant=tenant,
            url=str(request.url),
            user=verify_response.user,
            password=request.password,
        )

    async def resend_marketplace_otp(
        self, request: ResendMarketplaceOTPRequest
    ) -> dict:
        """Trigger SyftHub to resend a registration OTP."""
        async with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                await syfthub_client.resend_otp(email=request.email)
            except SyftHubError as e:
                raise e.to_http_exception() from e

        return {
            "message": (
                "If the email is registered and unverified, a new code was sent."
            )
        }

    async def _sync_public_url(self, syfthub_client: SyftHubClient) -> None:
        """Push the locally-configured public URL to SyftHub as the user's domain."""
        if app_settings.public_url:
            await syfthub_client.update_profile(domain=str(app_settings.public_url))

    async def _persist_marketplace_after_signup(
        self,
        *,
        tenant: Tenant,
        url: str,
        user: UserResponse,
        password: str,
    ) -> MarketplaceResponse:
        """Shared persistence path for register + verify-OTP + connect-new flows."""
        marketplace = await self.repository.create(
            Marketplace(
                tenant_id=tenant.id,
                name=user.full_name,
                username=user.username,
                url=url,
                email=user.email,
                password=password,
                is_default=False,
                is_active=True,
            )
        )

        if str(app_settings.default_marketplace_url) == url:
            marketplace = await self.repository.set_as_default(
                marketplace.id, tenant.id
            )

        return MarketplaceResponse.model_validate(marketplace)

    async def connect_marketplace(
        self, request: ConnectMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Connect to an existing SyftHub account and add as marketplace.

        Args:
            request: Marketplace connection request with existing credentials
            tenant: Tenant context

        Returns:
            Created marketplace
        """
        async with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                await syfthub_client.login(request.username, request.password)
                user_profile = await syfthub_client.profile()
                await self._sync_public_url(syfthub_client)
            except SyftHubError as e:
                raise e.to_http_exception() from e

        existing_marketplace = await self.repository.get_by_url(
            str(request.url), tenant.id
        )

        if existing_marketplace is None:
            return await self._persist_marketplace_after_signup(
                tenant=tenant,
                url=str(request.url),
                user=UserResponse(
                    username=user_profile.username,
                    email=user_profile.email,
                    full_name=user_profile.full_name,
                ),
                password=request.password,
            )

        marketplace = await self.repository.update(
            existing_marketplace.id,
            tenant.id,
            name=user_profile.full_name,
            username=user_profile.username,
            email=user_profile.email,
            password=request.password,
            is_active=True,
        )

        if app_settings.default_marketplace_url == request.url:
            marketplace = await self.repository.set_as_default(
                marketplace.id, tenant.id
            )

        return MarketplaceResponse.model_validate(marketplace)

    async def check_username_availability(self, url: str | None, username: str) -> bool:
        """Check if a username is available.

        Args:
            url: URL of the Marketplace
            username: Username to check

        Returns:
            True if username is available, False otherwise.
        """
        marketplace_url = (
            str(app_settings.default_marketplace_url) if url is None else url
        )
        async with SyftHubClient(marketplace_url) as syfthub_client:
            return await syfthub_client._is_username_available(username)

    async def list_marketplaces(
        self, tenant: Tenant, url: str | None = None
    ) -> list[MarketplaceListItem]:
        """List all marketplaces for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of marketplaces
        """
        marketplaces = await self.repository.get_all(tenant.id)
        return [MarketplaceListItem.model_validate(m) for m in marketplaces]

    async def get_marketplace(self, id: UUID, tenant: Tenant) -> MarketplaceResponse:
        """Get a specific marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant: Tenant context

        Returns:
            Marketplace details

        Raises:
            HTTPException: If marketplace not found
        """
        marketplace = await self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return MarketplaceResponse.model_validate(marketplace)

    async def delete_marketplace(self, id: UUID, tenant: Tenant) -> dict:
        """Delete a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If marketplace not found or is default marketplace
        """
        # Check if marketplace exists and is not default
        marketplace = await self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        if marketplace.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default marketplace (SyftHub)",
            )

        deleted = await self.repository.delete(id, tenant.id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return {"message": f"Successfully deleted marketplace '{marketplace.name}'"}

    async def get_default_marketplace(self, tenant: Tenant) -> Marketplace:
        """Get the default marketplace for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            Default marketplace

        Raises:
            HTTPException: If no default marketplace found
        """
        marketplace = await self.repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404,
                detail="No default marketplace configured. Please register with SyftHub first.",
            )
        return marketplace
