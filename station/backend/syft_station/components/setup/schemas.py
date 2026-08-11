"""Setup API schemas."""

import re

from pydantic import BaseModel, field_validator

_DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class SetupResponse(BaseModel):
    domain: str
    supported_version: str
    onboarded: bool
    station_host: str = ""
    """The station's own public host (from its ingress), shown at onboarding so
    the admin confirms rather than retypes it — spaces live at <subdomain> of
    it, optionally under a prefix. Empty when the station doesn't know its
    public URL (host-run dev), where the admin types the domain freely."""


class UpdateSetupRequest(BaseModel):
    domain: str | None = None
    supported_version: str | None = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not _DOMAIN_RE.match(v):
            raise ValueError("Enter a valid domain, e.g. spaces.my-station.org")
        return v
