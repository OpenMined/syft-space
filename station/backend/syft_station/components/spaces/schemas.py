"""Spaces API schemas."""

from datetime import datetime
from typing import Literal
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
    restart_required: bool
    created_at: datetime


class AdminUrlResponse(BaseModel):
    """The space URL with the admin API key attached as authToken —
    clicking it opens the space already signed in as its admin."""

    url: str


class SpaceStatusResponse(BaseModel):
    """Live runtime status of a space (read from Kubernetes, never stored)."""

    status: str


class SpaceLogsResponse(BaseModel):
    """A snapshot of the space container's recent log lines (newest last).

    Empty when the space has no running pod (paused or not yet up).
    """

    lines: list[str]


class SpaceUpdateResult(BaseModel):
    """One space's outcome in an update sweep."""

    space_id: UUID
    name: str
    outcome: Literal["updated", "skipped", "failed"]
    detail: str = ""


class UpdateAllResponse(BaseModel):
    supported_version: str
    results: list[SpaceUpdateResult]
