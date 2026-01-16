"""Marketplace handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException
from syft_accounting_sdk import ServiceException, UserClient

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.schemas import (
    BalanceResponse,
    ConnectMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
)
from syft_space.components.marketplaces.utils import (
    ensure_valid_accounting_credentials,
)
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
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
    ) -> MarketplaceResponse:
        """Register a new marketplace by creating a new SyftHub account.

        Args:
            request: Marketplace registration request
            tenant: Tenant context

        Returns:
            Created marketplace
        """
        async with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                user_profile = await syfthub_client.register(
                    username=request.username,
                    email=request.email,
                    full_name=request.name,
                    password=request.password,
                    accounting_service_url=str(request.accounting_url),
                    accounting_password=request.accounting_password,
                )

                # Login to get authenticated client for subsequent calls
                await syfthub_client.login(request.email, request.password)

                # Fetch accounting credentials from SyftHub
                accounting_creds = await syfthub_client.accounting_credentials()

                # If public URL is set, update the domain
                if app_settings.public_url:
                    await syfthub_client.update_profile(
                        domain=str(app_settings.public_url)
                    )

            except SyftHubError as e:
                raise e.to_http_exception() from e

        # Check if the marketplace should be set as default
        should_be_default = app_settings.default_marketplace_url == request.url

        # Create marketplace entity
        marketplace = Marketplace(
            tenant_id=tenant.id,
            name=user_profile.user.full_name,
            username=user_profile.user.username,
            url=str(request.url),
            email=user_profile.user.email,
            password=request.password,
            is_default=False,
            is_active=True,
            accounting_url=str(accounting_creds.url),
            accounting_email=accounting_creds.email,
            accounting_password=accounting_creds.password,
        )

        # Save to database
        marketplace = self.repository.create(marketplace)

        # Set as default if it matches the default marketplace URL
        if should_be_default:
            marketplace = self.repository.set_as_default(marketplace.id, tenant.id)

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
                # Login to existing account
                await syfthub_client.login(request.username, request.password)

                # Fetch user profile
                user_profile = await syfthub_client.profile()

                # Fetch accounting credentials
                accounting_creds = await syfthub_client.accounting_credentials()

                # Update domain if public URL is set
                if app_settings.public_url:
                    await syfthub_client.update_profile(
                        domain=str(app_settings.public_url)
                    )

            except SyftHubError as e:
                raise e.to_http_exception() from e

        # Check if the marketplace should be set as default
        should_be_default = app_settings.default_marketplace_url == request.url

        # Check if the marketplace already exists with the same URL
        existing_marketplace = self.repository.get_by_url(str(request.url), tenant.id)

        if existing_marketplace:
            # Update the marketplace with the new credentials
            marketplace = self.repository.update(
                existing_marketplace.id,
                tenant.id,
                name=user_profile.full_name,
                username=user_profile.username,
                email=user_profile.email,
                password=request.password,
                accounting_url=str(accounting_creds.url),
                accounting_email=accounting_creds.email,
                accounting_password=accounting_creds.password,
                is_active=True,
            )
        else:
            # Create marketplace entity with the new credentials
            marketplace = Marketplace(
                tenant_id=tenant.id,
                name=user_profile.full_name,
                username=user_profile.username,
                url=str(request.url),
                email=user_profile.email,
                password=request.password,
                is_default=False,
                is_active=True,
                accounting_url=str(accounting_creds.url),
                accounting_email=accounting_creds.email,
                accounting_password=accounting_creds.password,
            )
            marketplace = self.repository.create(marketplace)

        # Set as default if it matches the default marketplace URL
        if should_be_default:
            marketplace = self.repository.set_as_default(marketplace.id, tenant.id)

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

    def list_marketplaces(
        self, tenant: Tenant, url: str | None = None
    ) -> list[MarketplaceListItem]:
        """List all marketplaces for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of marketplaces
        """
        marketplaces = self.repository.get_all(tenant.id)
        return [MarketplaceListItem.model_validate(m) for m in marketplaces]

    def get_marketplace(self, id: UUID, tenant: Tenant) -> MarketplaceResponse:
        """Get a specific marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            tenant: Tenant context

        Returns:
            Marketplace details

        Raises:
            HTTPException: If marketplace not found
        """
        marketplace = self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return MarketplaceResponse.model_validate(marketplace)

    def delete_marketplace(self, id: UUID, tenant: Tenant) -> dict:
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
        marketplace = self.repository.get_by_id(id, tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        if marketplace.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default marketplace (SyftHub)",
            )

        deleted = self.repository.delete(id, tenant.id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return {"message": f"Successfully deleted marketplace '{marketplace.name}'"}

    def get_default_marketplace(self, tenant: Tenant) -> Marketplace:
        """Get the default marketplace for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            Default marketplace

        Raises:
            HTTPException: If no default marketplace found
        """
        marketplace = self.repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=404,
                detail="No default marketplace configured. Please register with SyftHub first.",
            )
        return marketplace

    async def get_balance(self, tenant: Tenant) -> BalanceResponse:
        """Get account balance for the default marketplace.

        Validates credentials before fetching balance, refreshing if needed.

        Args:
            tenant: Tenant context

        Returns:
            Balance response

        Raises:
            HTTPException: If no marketplace configured or balance fetch fails
        """
        marketplace = self.get_default_marketplace(tenant)

        # Validate and potentially refresh credentials using utility
        creds = await ensure_valid_accounting_credentials(marketplace, self.repository)

        try:
            accounting_client = UserClient(
                url=creds["url"],
                email=creds["email"],
                password=creds["password"],
            )
            user_info = accounting_client.get_user_info()
            return BalanceResponse(balance=user_info.balance)
        except ServiceException as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to get balance: {e.message}",
            ) from e
