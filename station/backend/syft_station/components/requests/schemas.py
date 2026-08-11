"""Space request API schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

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


class SubmitRequestBody(BaseModel):
    space_name: str
    subdomain: str
    reason: str = ""
    # Admin only: create the space for this member (ignored for members).
    owner_email: NormalizedEmail | None = None

    @field_validator("space_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Space name is required")
        return v

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        return v.strip()

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_slug(v)


class ApproveRequestBody(BaseModel):
    """Admin review-and-confirm: name/subdomain editable for conflicts."""

    space_name: str | None = None
    subdomain: str | None = None
    # Wallet picker: attach_wallet=False provisions without managed credits;
    # wallet_id=None means "the station wallet, if any" (the default entry).
    # An explicit id is validated — ready for multi-wallet later.
    attach_wallet: bool = True
    wallet_id: UUID | None = None

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_slug(v)


class RejectRequestBody(BaseModel):
    reason: str = ""


class RequestResponse(BaseModel):
    id: UUID
    space_name: str
    subdomain: str
    owner_email: str
    reason: str
    origin: str
    status: str
    reject_reason: str | None
    space_id: UUID | None
    created_at: datetime
    updated_at: datetime
