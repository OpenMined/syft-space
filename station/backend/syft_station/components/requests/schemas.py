"""Request API schemas.

Requests are typed: a submit carries a discriminated-union ``payload`` whose
``type`` selects the shape (create a space, delete a space, …). The handler
dispatches on that type. Approve/reject/withdraw are generic across types.
"""

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from syft_station.components.shared.email import NormalizedEmail

# DNS-1123 label: lowercase alphanumeric + hyphens, no leading/trailing
# hyphen, ≤63 chars (same rule as the frontend's slugify).
_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def slugify(name: str) -> str:
    """Derive a DNS-1123 label from a display name."""
    slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:63].rstrip("-")


def validate_slug(v: str) -> str:
    v = v.strip().lower()
    if not _SLUG_RE.match(v):
        raise ValueError(
            "Subdomain must be a DNS-1123 label: lowercase letters, digits "
            "and hyphens, not starting/ending with a hyphen, max 63 chars"
        )
    return v


# ── Per-type submit payloads (discriminated on `type`) ──────────────────────


class CreateSpacePayload(BaseModel):
    type: Literal["create_space"] = "create_space"
    space_name: str
    subdomain: str

    @field_validator("space_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Space name is required")
        return v

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_slug(v)


class DeleteSpacePayload(BaseModel):
    type: Literal["delete_space"] = "delete_space"
    # The target space is named by the envelope's space_id; nothing else.


RequestPayload = Annotated[
    CreateSpacePayload | DeleteSpacePayload,
    Field(discriminator="type"),
]


class SubmitRequestBody(BaseModel):
    """Submit any request type. `payload.type` selects the shape.

    `space_id` targets an existing space (required by delete_space, ignored by
    create_space). `owner_email` is admin-only — submit on a member's behalf.
    """

    payload: RequestPayload
    reason: str = ""
    space_id: UUID | None = None
    owner_email: NormalizedEmail | None = None

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        return v.strip()


class ApproveRequestBody(BaseModel):
    """Admin approve. For create_space, name/subdomain are editable (conflict
    resolution) and the wallet is picked; ignored by other types."""

    space_name: str | None = None
    subdomain: str | None = None
    attach_wallet: bool = True
    wallet_id: UUID | None = None

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str | None) -> str | None:
        return None if v is None else validate_slug(v)


class RejectRequestBody(BaseModel):
    reason: str = ""


class RequestResponse(BaseModel):
    id: UUID
    type: str
    status: str
    owner_email: str
    space_id: UUID | None
    space_name: str | None
    subdomain: str | None
    reason: str
    resolution_note: str | None
    payload: dict
    origin: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
