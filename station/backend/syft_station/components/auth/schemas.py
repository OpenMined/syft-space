"""Auth API schemas."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str = Field(
        min_length=1, description="Google ID token (JWT) from Google Sign-In"
    )


class AuthConfigResponse(BaseModel):
    """Public sign-in config the frontend reads before authenticating."""

    google_enabled: bool
    google_client_id: str


class MeResponse(BaseModel):
    email: str
    username: str
    name: str
    role: str


class LogoutResponse(BaseModel):
    message: str = "Signed out"
