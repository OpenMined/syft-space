"""Spaces API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SpaceResponse(BaseModel):
    id: UUID
    request_id: UUID | None
    name: str
    subdomain: str
    owner_email: str
    url: str
    version: str
    created_at: datetime


class TokenRevealResponse(BaseModel):
    """One-time reveal of the space admin API key."""

    token: str


class TokenStatusResponse(BaseModel):
    revealed: bool
    created_at: datetime


class SpaceStatusResponse(BaseModel):
    """Live runtime status of a space (read from Kubernetes, never stored)."""

    status: str
