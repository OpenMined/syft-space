"""Response models for the SyftHub API."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class SlugAvailability(BaseModel):
    """The Hub's answer to "could I publish under this slug right now?"."""

    available: bool
    reason: str | None = None  # why not, for a person; None when available


class TokenResponse(BaseModel):
    """Response from login/refresh endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User information from registration."""

    username: str
    email: str
    full_name: str


class RegisterResponse(BaseModel):
    """Response from registration endpoint.

    When SyftHub has SMTP configured, registration becomes a two-step flow:
    tokens come back null and ``requires_email_verification`` is True. The
    client must then call ``/auth/register/verify-otp`` with the code emailed
    to the user before tokens are issued.
    """

    user: UserResponse
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    requires_email_verification: bool = False


class VerifyOTPResponse(BaseModel):
    """Response from /auth/register/verify-otp on SyftHub."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccountingResponse(BaseModel):
    """Response from accounting endpoint."""

    url: HttpUrl
    email: EmailStr
    password: str


class EndpointResponse(BaseModel):
    """Response from publish endpoint."""

    id: str
    name: str
    # Add other fields as needed

    model_config = {"extra": "allow"}


class UserProfile(BaseModel):
    """User profile from SyftHub."""

    username: str = Field(..., description="Username")
    email: str = Field(..., description="Login email")
    full_name: str = Field(..., description="Full name")
    password: str | None = Field(None, description="Login password")
    domain: str | None = Field(None, description="Domain")


class SatelliteKind(StrEnum):
    """What a satellite serves. The hub matches on origin alone; this is a label."""

    SPACE = "space"
    STATION = "station"


class Satellite(BaseModel):
    """A marketplace registry row for one origin owned by one account."""

    id: UUID
    kind: SatelliteKind
    base_url: str = Field(
        ...,
        description="Origin, canonicalised by the marketplace. Not a URL type: "
        "`tunneling:<username>` is legal here",
    )
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


class SatelliteToken(BaseModel):
    """Response from verify satellite token endpoint."""

    valid: bool = Field(..., description="True if token is valid, False otherwise.")
    email: EmailStr | None = Field(None, description="User email")
    iat: int | None = Field(None, description="Issued at time")
    exp: int | None = Field(None, description="Expiration time")
    aud: str | None = Field(None, description="Satellite the token was minted for")
    sub: str | None = Field(None, description="Subject; 'guest' for guest tokens")
    username: str | None = None
    role: str | None = None
    error: str | None = Field(None, description="Failure kind when valid is False")
    message: str | None = None

    class Config:
        """Pydantic config."""

        from_attributes = True

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.exp is None or self.iat is None:
            return True
        return self.exp < self.iat


class TunnelCredentialsResponse(BaseModel):
    """Response from tunnel credentials endpoint."""

    auth_token: str = Field(..., description="Ngrok authentication token")
    domain: str = Field(..., description="Ngrok tunnel domain")
