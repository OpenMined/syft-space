"""Narrow read-only Protocols the policies layer depends on.

The CapabilityChecker reads wallets, endpoints, and sibling policies to
verify that a policy can be attached. It depends on these narrow Protocols
rather than on the concrete `WalletRepository` / `EndpointRepository` /
`PolicyRepository` classes — that gives us:

- DIP: the policies layer owns its abstractions; concrete repos in other
  components satisfy them structurally.
- ISP: each Protocol exposes only the single method the checker uses; the
  full repository surface is irrelevant here.

Concrete repositories already match these shapes — no changes required
to satisfy these Protocols.
"""

from typing import Protocol
from uuid import UUID

from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.wallets.entities import Wallet


class WalletLookup(Protocol):
    """Fetch a wallet by id within a tenant."""

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Wallet | None: ...


class EndpointLookup(Protocol):
    """Fetch an endpoint by id within a tenant."""

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Endpoint | None: ...


class EndpointPolicyQuery(Protocol):
    """Answer questions about policies attached to a given endpoint."""

    async def has_different_wallet(
        self, endpoint_id: UUID, tenant_id: UUID, wallet_id: UUID
    ) -> bool: ...
