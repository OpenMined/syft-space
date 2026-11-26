from collections.abc import Callable, Coroutine

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

from syft_space.components.auth.satellite_tokens import SatelliteTokenVerifier
from syft_space.components.marketplaces.repository import (
    Marketplace,
    MarketplaceRepository,
)
from syft_space.components.shared.telemetry import set_request_attributes
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings

# Security scheme for OpenAPI documentation
# Actual auth is handled by AdminKeyMiddleware
bearer_scheme = HTTPBearer(
    auto_error=False,  # Don't raise error - middleware handles it
    description="Admin API key or SyftHub satellite token",
)


async def get_verified_user_email(
    request: Request,
    marketplace: Marketplace,
    verifier: SatelliteTokenVerifier,
) -> str:
    """Extract and verify SyftHub satellite token.

    Verified locally against the marketplace's public keys; the marketplace
    is called only when that cannot settle it (see ``satellite_tokens``).

    Args:
        request: FastAPI request object
        marketplace: Marketplace
        verifier: Verifies the satellite token

    Returns:
        Verified user's email address

    Raises:
        HTTPException: 401 if token missing/invalid/expired
        HTTPException: 400 if no marketplace configured
        HTTPException: 503 if the marketplace had to be asked and is unreachable
    """
    # Extract Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = auth_header[7:]

    # Validate marketplace credentials are set
    if not marketplace.email or not marketplace.password:
        raise HTTPException(
            status_code=424, detail="Marketplace credentials are not set"
        )

    # If Token is Admin API Key, return admin email from marketplace
    if token == app_settings.admin_api_key:
        return marketplace.email

    set_request_attributes(endpoint_slug=request.path_params.get("slug"))
    return await verifier.email_for(token, marketplace)


# Type alias for the dependency callable used by route builders
get_verified_sender_email_dependency = Callable[..., Coroutine[None, None, str]]


def make_verified_sender_email_dependency(
    marketplace_repository: MarketplaceRepository,
    verifier: SatelliteTokenVerifier,
) -> get_verified_sender_email_dependency:
    """Create the FastAPI dependency that returns the caller's verified email."""

    async def get_verified_sender_email(
        request: Request,
        tenant: Tenant = Depends(get_tenant_dependency),
    ) -> str:
        marketplace = await marketplace_repository.get_default(tenant.id)
        if not marketplace:
            raise HTTPException(status_code=400, detail="No marketplace configured")
        return await get_verified_user_email(request, marketplace, verifier)

    return get_verified_sender_email
