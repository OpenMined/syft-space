"""Marketplace handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException
from syft_accounting_sdk import ServiceException, UserClient

from syftai_space.components.marketplaces.entities import Marketplace
from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.marketplaces.schemas import (
    BalanceResponse,
    ConnectMarketplaceRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
    UpdateMarketplaceRequest,
)
from syftai_space.components.marketplaces.utils import (
    ensure_valid_accounting_credentials,
)
from syftai_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syftai_space.components.tenants.entities import Tenant
from syftai_space.config import app_settings


class MarketplaceHandler:
    """Handler for marketplace business logic."""

    def __init__(self, repository: MarketplaceRepository):
        """Initialize the marketplace handler.

        Args:
            repository: Marketplace repository
        """
        self.repository = repository

    def register_marketplace(
        self, request: RegisterMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Register a new marketplace by creating a new SyftHub account.

        Args:
            request: Marketplace registration request
            tenant: Tenant context

        Returns:
            Created marketplace
        """
        with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                user_profile = syfthub_client.register(
                    username=request.username,
                    email=request.email,
                    full_name=request.name,
                    password=request.password,
                    accounting_service_url=str(request.accounting_url),
                )

                # Login to get authenticated client for subsequent calls
                syfthub_client.login(request.email, request.password)

                # Fetch accounting credentials from SyftHub
                accounting_creds = syfthub_client.accounting_credentials()

                # If public URL is set, update the domain
                if app_settings.public_url:
                    syfthub_client.update_profile(domain=str(app_settings.public_url))

            except SyftHubError as e:
                raise e.to_http_exception() from e

        # Check if the marketplace should be set as default
        # If the default marketplace URL is the same as the marketplace URL,
        # set it as default
        # HttpUrl types are automatically normalized by Pydantic, so direct comparison works
        set_as_default = app_settings.default_marketplace_url == request.url

        # Create marketplace entity
        marketplace = Marketplace(
            tenant_id=tenant.id,
            name=user_profile.user.full_name,
            username=user_profile.user.username,
            url=str(request.url),
            email=user_profile.user.email,
            password=request.password,
            is_default=set_as_default,
            is_active=True,
            # Accounting credentials from SyftHub
            accounting_url=str(accounting_creds.url),
            accounting_email=accounting_creds.email,
            accounting_password=accounting_creds.password,
        )

        # Save to database
        created = self.repository.create(marketplace)

        return MarketplaceResponse.model_validate(created)

    def connect_marketplace(
        self, request: ConnectMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Connect to an existing SyftHub account and add as marketplace.

        Args:
            request: Marketplace connection request with existing credentials
            tenant: Tenant context

        Returns:
            Created marketplace
        """
        with SyftHubClient(str(request.url)) as syfthub_client:
            try:
                # Login to existing account
                syfthub_client.login(request.username, request.password)

                # Fetch user profile
                user_profile = syfthub_client.profile()

                # Fetch accounting credentials
                accounting_creds = syfthub_client.accounting_credentials()

                # Update domain if public URL is set
                if app_settings.public_url:
                    syfthub_client.update_profile(domain=str(app_settings.public_url))

            except SyftHubError as e:
                raise e.to_http_exception() from e

        # Check if the marketplace should be set as default
        # HttpUrl types are automatically normalized by Pydantic, so direct comparison works
        set_as_default = app_settings.default_marketplace_url == request.url

        # TODO: Add check if marketplace already exists, if so, update it instead of creating a new one

        # Create marketplace entity
        marketplace = Marketplace(
            tenant_id=tenant.id,
            name=user_profile.full_name,
            username=user_profile.username,
            url=str(request.url),
            email=user_profile.email,
            password=request.password,  # Store for future logins
            is_default=set_as_default,
            is_active=True,
            # Accounting credentials from SyftHub
            accounting_url=str(accounting_creds.url),
            accounting_email=accounting_creds.email,
            accounting_password=accounting_creds.password,
        )

        # Save to database
        created = self.repository.create(marketplace)

        return MarketplaceResponse.model_validate(created)

    def check_username_availability(self, url: str | None, username: str) -> bool:
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
        with SyftHubClient(marketplace_url) as syfthub_client:
            return syfthub_client._is_username_available(username)

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

    def update_marketplace(
        self, id: UUID, request: UpdateMarketplaceRequest, tenant: Tenant
    ) -> MarketplaceResponse:
        """Update a marketplace by ID within a tenant.

        Args:
            id: Marketplace ID
            request: Update request with fields to update
            tenant: Tenant context

        Returns:
            Updated marketplace details

        Raises:
            HTTPException: If marketplace not found
        """
        # Convert URL to string if provided
        url_str = str(request.url) if request.url else None

        updated = self.repository.update(
            id,
            tenant.id,
            name=request.name,
            url=url_str,
            email=request.email,
            password=request.password,
            username=request.username,
            is_active=request.is_active,
        )

        if not updated:
            raise HTTPException(
                status_code=404, detail=f"Marketplace with ID '{id}' not found"
            )

        return MarketplaceResponse.model_validate(updated)

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

    def get_balance(self, tenant: Tenant) -> BalanceResponse:
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
        creds = ensure_valid_accounting_credentials(marketplace, self.repository)

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
