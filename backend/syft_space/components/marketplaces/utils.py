"""Marketplace utility functions."""

import asyncio

from fastapi import HTTPException
from syft_accounting_sdk import ServiceException, UserClient

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError


async def refresh_accounting_credentials(
    marketplace: Marketplace,
    repository: MarketplaceRepository,
) -> dict[str, str]:
    """Refresh accounting credentials from SyftHub.

    Args:
        marketplace: Marketplace to refresh credentials for
        repository: Repository to update credentials

    Returns:
        Fresh accounting credentials dict

    Raises:
        HTTPException: If refresh fails
    """
    try:
        async with SyftHubClient(marketplace.url) as syfthub_client:
            await syfthub_client.login(marketplace.email, marketplace.password)
            creds = await syfthub_client.accounting_credentials()
    except SyftHubError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Failed to refresh accounting credentials: {e.message}",
        ) from e

    # Update marketplace with fresh credentials
    await repository.update(
        marketplace.id,
        marketplace.tenant_id,
        accounting_url=str(creds.url),
        accounting_email=creds.email,
        accounting_password=creds.password,
    )

    return {
        "url": str(creds.url),
        "email": creds.email,
        "password": creds.password,
    }


async def ensure_valid_accounting_credentials(
    marketplace: Marketplace,
    repository: MarketplaceRepository,
) -> dict[str, str]:
    """Validate accounting credentials and refresh if expired.

    Attempts to validate credentials by calling the accounting service.
    If validation fails with 401, refreshes credentials from SyftHub.

    Args:
        marketplace: Marketplace with accounting credentials
        repository: Repository to update credentials if refreshed

    Returns:
        Valid accounting credentials dict

    Raises:
        HTTPException: If validation and refresh both fail
    """
    creds = {
        "url": marketplace.accounting_url,
        "email": marketplace.accounting_email,
        "password": marketplace.accounting_password,
    }

    # Skip validation if credentials are empty
    if not creds["url"] or not creds["email"] or not creds["password"]:
        raise HTTPException(
            status_code=400,
            detail="Accounting credentials not configured for this marketplace.",
        )

    # Try to validate credentials by calling the accounting SDK
    try:
        accounting_client = UserClient(
            url=creds["url"],
            email=creds["email"],
            password=creds["password"],
        )
        # Blocking SDK call wrapped with to_thread
        await asyncio.to_thread(accounting_client.get_user_info)
        return creds
    except ServiceException as e:
        # Check if it's an authentication error
        if e.status_code == 401:
            # Refresh credentials from SyftHub and return fresh ones
            return await refresh_accounting_credentials(marketplace, repository)

        raise HTTPException(
            status_code=e.status_code,
            detail=f"Failed to validate accounting credentials: {e.message}",
        ) from e
