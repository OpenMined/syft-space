"""Seams the credits component depends on (consumer-owned interfaces).

The wallet rollout walks the space registry and patches k8s Secrets, but
the credits component never imports the spaces component — it declares the
minimal shape it needs here, and the spaces repository satisfies it
structurally.
"""

from typing import Protocol
from uuid import UUID


class SpaceRecord(Protocol):
    """The slice of a space the credits component reads and writes."""

    id: UUID
    name: str
    subdomain: str
    owner_email: str
    wallet_id: UUID | None
    wallet_opt_out: bool
    restart_required: bool


class SpaceDirectory(Protocol):
    """Registry access for the wallet rollout."""

    async def get_all(self) -> list[SpaceRecord]: ...

    async def update(self, space: SpaceRecord) -> SpaceRecord: ...


class SpaceIdentity(Protocol):
    """Who a space is (or was): the attribution money views render."""

    name: str
    subdomain: str
    owner_email: str
    deleted: bool


class SpaceIdentities(Protocol):
    """Attribution lookup for money views, keyed by space id.

    Deleting a space removes only its registry row — the ledger keeps
    earning in the space's name, so this lookup must also resolve deleted
    spaces (the request rows they were born from are never deleted).
    """

    async def space_identities(self) -> dict[UUID, SpaceIdentity]: ...


class SecretPatcher(Protocol):
    """The provisioner slice the rollout needs: patch the Secret, then
    restart the space so the patch takes effect."""

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        """Merge keys into the space's Secret (applies on restart)."""
        ...

    async def restart(self, subdomain: str) -> None:
        """Roll the space's pods so they start with the current Secret."""
        ...
