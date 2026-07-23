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


class AdminUrlResponse(BaseModel):
    """The space URL with the admin API key attached as authToken —
    clicking it opens the space already signed in as its admin."""

    url: str


class SpaceStatusResponse(BaseModel):
    """Live runtime status of a space (read from Kubernetes, never stored)."""

    status: str
