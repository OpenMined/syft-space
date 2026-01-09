from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer

from syftai_space.components.marketplaces.repository import Marketplace
from syftai_space.components.shared.syfthub_client import SyftHubError
from syftai_space.config import app_settings

# Security scheme for OpenAPI documentation
# Actual auth is handled by AdminKeyMiddleware
bearer_scheme = HTTPBearer(
    auto_error=False,  # Don't raise error - middleware handles it
    description="Admin API key or SyftHub satellite token",
)


def get_verified_user_email(
    request: Request,
    marketplace: Marketplace,
) -> str:
    """Extract and verify SyftHub satellite token.

    Uses handler.marketplace_repository captured from closure.

    Args:
        request: FastAPI request object
        marketplace: Marketplace

    Returns:
        Verified user's email address

    Raises:
        HTTPException: 401 if token missing/invalid/expired
        HTTPException: 400 if no marketplace configured
        HTTPException: 500 if verification fails
    """
    from syftai_space.components.shared.syfthub_client import SyftHubClient

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

    # Otherwise, verify token with SyftHub
    try:
        client = SyftHubClient(str(marketplace.url))
        client.login(marketplace.email, marketplace.password)
        result = client.verify_satellite_token(token)
    except SyftHubError as e:
        raise e.to_http_exception() from e

    if not result.valid:
        raise HTTPException(status_code=401, detail="Invalid satellite token")
    if result.is_expired:
        raise HTTPException(status_code=401, detail="Satellite token expired")
    if not result.email:
        raise HTTPException(status_code=401, detail="Token missing email claim")

    return str(result.email)
