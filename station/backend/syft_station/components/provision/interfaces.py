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
    wallet_id: str  # the space adopts this so all spaces on the wallet share one id
    public_url: str  # station's public base URL, published on paid endpoints
    wallet_owner: str  # SyftHub user id of the wallet owner; "" if it has none
    bundles: str  # JSON [{"name", "amount"}, …] price list; "" if none exists


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
    # Rendered into the space Secret as SYFT_CLUSTER_CREDITS_{URL,TOKEN,CURRENCY,
    # WALLET_ID}, SYFT_CLUSTER_PUBLIC_URL, SYFT_CLUSTER_WALLET_OWNER, and
    # SYFT_CLUSTER_BUNDLES.
    credits_url: str = ""
    credits_token: str = ""
    credits_currency: str = ""
    credits_wallet_id: str = ""
    credits_public_url: str = ""
    credits_wallet_owner: str = ""
    credits_bundles: str = ""


class Provisioner(Protocol):
    async def provision(self, spec: SpaceSpec) -> str:
        """Stand up the space; returns its public URL.

        Raises ProvisionError on failure.
        """
        ...

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        """Tear down the space; purge=False retains its data volume."""
        ...

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        """Merge keys into the space's Secret (no restart — the running pod
        keeps its env until the space is restarted)."""
        ...

    async def restart(self, subdomain: str) -> None:
        """Roll the space's pods so they start with the current Secret.

        Fire-and-forget: returns once the roll is triggered; progress is
        visible through get_status.
        """
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
