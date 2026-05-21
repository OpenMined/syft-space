"""Wallet provider interfaces (gateway boundary).

Defines the WalletProvider Protocol — the adapter boundary between the
use case layer (WalletHandler) and concrete wallet adapters
(MppWalletProvider, XenditWalletProvider, etc.).

Following Clean Architecture:
- The Protocol is defined in the use case layer
- Concrete adapters implement it in the adapter layer
- The handler depends on the Protocol, never on concrete adapters
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel


@dataclass
class SetupResult:
    """Result of a wallet setup operation.

    Returned by WalletProvider.setup_wallet().
    """

    credentials: dict[str, Any]
    """Validated credentials + provider-specific config to store in Wallet.configuration."""

    currency: str
    """Wallet currency code, surfaced to the entity (queryable, uniqueness key)."""

    country: str | None = None
    """Optional country code (ISO 3166-1 alpha-2). Region-specific providers only."""

    display: dict[str, Any] = field(default_factory=dict)
    """Type-specific info for the frontend.

    MPP: {"wallet_address": "0x..."}
    Xendit: {"webhook_url": "https://..."}
    """


class WalletProvider(Protocol):
    """Gateway interface for wallet type operations.

    All wallet types implement this Protocol. It handles credential
    setup only — balance/transactions are a separate concern in
    the payments component.
    """

    NAME: str

    @property
    def config_class(self) -> type[BaseModel]:
        """Return the Pydantic config class for this wallet type."""
        ...

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        """Create or import wallet credentials.

        The provider decides internally how to handle the input:
        - MPP: {} → generate keypair, {"private_key": "0x..."} → import
        - Xendit: {"api_key": "...", "callback_token": "..."} → validate

        Returns:
            SetupResult with credentials to persist and display info for frontend.
        """
        ...

    def extract_display(
        self, configuration: dict[str, Any], wallet_id: UUID
    ) -> dict[str, Any]:
        """Extract safe display info from stored configuration.

        Called on every get/list to build the response. Must never expose
        secrets (private keys, API keys, tokens).

        ``wallet_id`` is provided so providers can compute wallet-scoped
        URLs (e.g. Stripe's webhook URL includes the wallet id to look up
        the signing secret before parsing the untrusted body). Providers
        whose display info is wallet-id-independent (Xendit, MPP) may
        ignore it.
        """
        ...

    def update_credentials(
        self,
        current_config: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply partial updates to stored credentials.

        Returns the full updated configuration dict.
        Raises ValueError if the update is invalid for this wallet type.

        Default: not supported (raises ValueError).
        """
        ...
