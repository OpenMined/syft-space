"""Auth API schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    email: str
    username: str
    name: str
    role: str


class LogoutResponse(BaseModel):
    message: str = "Signed out"
