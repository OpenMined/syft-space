"""Seams the credits component depends on (consumer-owned interfaces).

The wallet rollout walks the space registry and patches k8s Secrets, but
the credits component never imports the spaces component — it declares the
minimal shape it needs here, and the spaces repository satisfies it
structurally.
"""

from typing import Protocol
from uuid import UUID


class SpaceRecord(Protocol):
    """The slice of a space the wallet rollout reads and writes."""

    id: UUID
    subdomain: str
    wallet_id: UUID | None
    wallet_opt_out: bool


class SpaceDirectory(Protocol):
    """Registry access for the wallet rollout."""

    async def get_all(self) -> list[SpaceRecord]: ...

    async def update(self, space: SpaceRecord) -> SpaceRecord: ...


class SecretPatcher(Protocol):
    """The one provisioner capability the rollout needs."""

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        """Merge keys into the space's Secret (applies on restart)."""
        ...
