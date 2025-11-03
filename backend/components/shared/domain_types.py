"""Shared domain types used across the application."""

from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class Context(BaseModel):
    """Context for requests across all type systems."""

    sender: EmailStr = Field(..., description="Email of the sender")


class HealthcheckStatus(str, Enum):
    """Status for healthcheck responses."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthcheckResponse(BaseModel):
    """Standard healthcheck response."""

    status: HealthcheckStatus = Field(..., description="Health status")
    message: str = Field(default="", description="Optional status message")
