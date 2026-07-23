"""Provisioner seam — the station's only contact with the substrate.

MockProvisioner runs without a cluster (fast dev + tests); K8sProvisioner is
the real one, behind the same protocol. The contract with syft-space is the
container image + SYFT_* env vars + health endpoint — nothing else.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class ProvisionError(Exception):
    """Provisioning failed; the request should move to FAILED."""


@dataclass(frozen=True)
class CreditsGrant:
    """What a space needs to use the station as its accounting service.

    Produced by the credits component, consumed into SpaceSpec — lives here
    (next to the spec it feeds) so neither side needs the other's internals.
    """

    url: str
    token: str  # plaintext — destined for the space's k8s Secret only
    currency: str


class SpaceRuntimeStatus(StrEnum):
    """Live running state of a space, read from the substrate (never stored).

    RUNNING = at least one pod up; PAUSED = scaled to 0 (data kept, compute
    freed); UNAVAILABLE = desired but no pod ready (starting or unhealthy);
    NOT_FOUND = no deployment (e.g. never provisioned, or torn down).
    """

    RUNNING = "running"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"


class SpaceSpec(BaseModel):
    """Everything a provisioner needs to stand up one space."""

    subdomain: str
    space_name: str
    owner_email: str
    version: str
    domain: str
    admin_token: str
    # Managed credits (all-or-nothing; empty token = space has no wallet).
    # Rendered into the space Secret as SYFT_CLUSTER_CREDITS_{URL,TOKEN,CURRENCY}.
    credits_url: str = ""
    credits_token: str = ""
    credits_currency: str = ""


class Provisioner(Protocol):
    async def provision(self, spec: SpaceSpec) -> str:
        """Stand up the space; returns its public URL.

        Raises ProvisionError on failure.
        """
        ...

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        """Tear down the space; purge=False retains its data volume."""
        ...

    async def pause(self, subdomain: str) -> None:
        """Free the space's compute (scale to 0); keep its data."""
        ...

    async def resume(self, subdomain: str) -> None:
        """Bring a paused space back (scale to 1)."""
        ...

    async def get_status(self, subdomain: str) -> SpaceRuntimeStatus:
        """Read the space's live running state from the substrate."""
        ...
