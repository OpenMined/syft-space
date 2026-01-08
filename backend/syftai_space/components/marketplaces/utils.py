"""Marketplace utility functions."""

from fastapi import HTTPException
from syft_accounting_sdk import ServiceException, UserClient

from syftai_space.components.marketplaces.entities import Marketplace
from syftai_space.components.marketplaces.repository import MarketplaceRepository
from syftai_space.components.shared.syfthub_client import SyftHubClient


def refresh_accounting_credentials(
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
        syfthub_client = SyftHubClient(marketplace.url)
        syfthub_client.login(marketplace.email, marketplace.password)
        creds = syfthub_client.accounting_credentials()

        # Update marketplace with fresh credentials
        repository.update(
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
    except Exception as e:
        raise HTTPException(
            status_code=getattr(e, "status_code", 500),
            detail=f"Failed to refresh accounting credentials: {getattr(e, 'message', str(e))}",
        ) from e


def ensure_valid_accounting_credentials(
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
        # Call get_user_info to validate credentials
        accounting_client.get_user_info()
        return creds
    except ServiceException as e:
        # Check if it's an authentication error
        if e.status_code == 401:
            # Refresh credentials from SyftHub and return fresh ones
            return refresh_accounting_credentials(marketplace, repository)

        raise HTTPException(
            status_code=e.status_code,
            detail=f"Failed to validate accounting credentials: {e.message}",
        ) from e
