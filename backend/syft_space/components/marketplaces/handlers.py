"""Marketplace handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.schemas import (
    BalanceResponse,
    ConnectMarketplaceRequest,
    CreateWalletResponse,
    ImportWalletRequest,
    MarketplaceListItem,
    MarketplaceResponse,
    RegisterMarketplaceRequest,
    TransactionResponse,
    UpdateWalletAddressRequest,
    WalletResponse,
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
                )

                # Login to get authenticated client for subsequent calls
                await syfthub_client.login(request.email, request.password)

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
        )

        # Save to database
        marketplace = await self.repository.create(marketplace)

        # Set as default if it matches the default marketplace URL
        if should_be_default:
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
                # Login to existing account
                await syfthub_client.login(request.username, request.password)

                # Fetch user profile
                user_profile = await syfthub_client.profile()

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
        existing_marketplace = await self.repository.get_by_url(
            str(request.url), tenant.id
        )

        if existing_marketplace:
            # Update the marketplace with the new credentials
            marketplace = await self.repository.update(
                existing_marketplace.id,
                tenant.id,
                name=user_profile.full_name,
                username=user_profile.username,
                email=user_profile.email,
                password=request.password,
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
            )
            marketplace = await self.repository.create(marketplace)

        # Set as default if it matches the default marketplace URL
        if should_be_default:
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

    async def get_balance(self, tenant: Tenant) -> BalanceResponse:
        """Get account balance for the default marketplace.

        If the marketplace has a wallet_address configured, queries the Tempo
        blockchain directly. Otherwise, returns a zero balance.

        Args:
            tenant: Tenant context

        Returns:
            Balance response

        Raises:
            HTTPException: If no marketplace configured or balance fetch fails
        """
        marketplace = await self.get_default_marketplace(tenant)

        # If wallet is configured, query Tempo blockchain
        if marketplace.wallet_address:
            from syft_space.components.marketplaces.tempo_utils import (
                get_wallet_balance,
                get_wallet_transactions,
            )

            balance = await get_wallet_balance(marketplace.wallet_address)
            recent_txs = await get_wallet_transactions(marketplace.wallet_address)
            return BalanceResponse(
                balance=balance,
                currency="USD",
                recent_transactions=[
                    TransactionResponse(**tx) for tx in recent_txs[:10]
                ],
                wallet_configured=True,
            )

        # No wallet configured
        return BalanceResponse(
            balance=0.0,
            currency="USD",
            recent_transactions=[],
            wallet_configured=False,
        )

    async def get_transactions(self, tenant: Tenant) -> list[TransactionResponse]:
        """Get all transactions for the default marketplace.

        If the marketplace has a wallet_address configured, queries the Tempo
        blockchain directly. Otherwise, returns an empty list.

        Args:
            tenant: Tenant context

        Returns:
            List of all transactions sorted by date descending

        Raises:
            HTTPException: If no marketplace configured or fetch fails
        """
        marketplace = await self.get_default_marketplace(tenant)

        # If wallet is configured, query Tempo blockchain
        if marketplace.wallet_address:
            from syft_space.components.marketplaces.tempo_utils import (
                get_wallet_transactions,
            )

            txs = await get_wallet_transactions(marketplace.wallet_address)
            return [TransactionResponse(**tx) for tx in txs]

        # No wallet configured
        return []

    async def get_wallet(self, tenant: Tenant) -> WalletResponse:
        """Get wallet info for the default marketplace."""
        marketplace = await self.repository.get_default(tenant.id)
        if not marketplace:
            return WalletResponse(address=None, exists=False)
        return WalletResponse(
            address=marketplace.wallet_address,
            exists=marketplace.wallet_address is not None,
        )

    async def create_wallet(self, tenant: Tenant) -> CreateWalletResponse:
        """Generate a new Tempo wallet keypair."""
        from eth_account import Account
        from mpp.methods.tempo import TempoAccount

        marketplace = await self.repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=400, detail="No default marketplace configured"
            )

        acct = Account.create()
        tempo_acct = TempoAccount.from_key(acct.key.hex())

        await self.repository.update(
            marketplace.id,
            tenant.id,
            wallet_address=tempo_acct.address,
            wallet_private_key=tempo_acct.private_key,
        )

        return CreateWalletResponse(address=tempo_acct.address)

    async def import_wallet(
        self, request: ImportWalletRequest, tenant: Tenant
    ) -> CreateWalletResponse:
        """Import an existing wallet from private key."""
        from mpp.methods.tempo import TempoAccount

        marketplace = await self.repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=400, detail="No default marketplace configured"
            )

        try:
            tempo_acct = TempoAccount.from_key(request.private_key)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid private key: {e}"
            ) from e

        await self.repository.update(
            marketplace.id,
            tenant.id,
            wallet_address=tempo_acct.address,
            wallet_private_key=tempo_acct.private_key,
        )

        return CreateWalletResponse(address=tempo_acct.address)

    async def update_wallet_address(
        self, request: UpdateWalletAddressRequest, tenant: Tenant
    ) -> WalletResponse:
        """Update wallet address manually (without private key)."""
        marketplace = await self.repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(
                status_code=400, detail="No default marketplace configured"
            )

        await self.repository.update(
            marketplace.id,
            tenant.id,
            wallet_address=request.wallet_address,
        )

        return WalletResponse(address=request.wallet_address, exists=True)
