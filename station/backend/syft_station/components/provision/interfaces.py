"""Provisioner seam — the station's only contact with the substrate.

C1 ships DevProvisioner; the Kubernetes implementation (C2) replaces it
behind the same protocol. The contract with syft-space is the container
image + SYFT_* env vars + health endpoint — nothing else.
"""

from typing import Protocol

from pydantic import BaseModel


class ProvisionError(Exception):
    """Provisioning failed; the request should move to FAILED."""


class SpaceSpec(BaseModel):
    """Everything a provisioner needs to stand up one space."""

    subdomain: str
    space_name: str
    owner_email: str
    version: str
    domain: str
    admin_token: str


class Provisioner(Protocol):
    async def provision(self, spec: SpaceSpec) -> str:
        """Stand up the space; returns its public URL.

        Raises ProvisionError on failure.
        """
        ...

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        """Tear down the space; purge=False retains its data volume."""
        ...
