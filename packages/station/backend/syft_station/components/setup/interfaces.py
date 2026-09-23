"""Seams the setup component depends on (consumer-owned interfaces).

Changing the station's SyftHub identity changes a fact every attached space
publishes, but the setup component never imports the spaces component — it
declares the one call it needs here, and the spaces repository satisfies it
structurally.
"""

from typing import Protocol
from uuid import UUID


class SpaceFlags(Protocol):
    """Flag the spaces carrying wallet facts that have just changed."""

    async def flag_wallet_stale(
        self, message: str, wallet_id: UUID | None = None
    ) -> int: ...
