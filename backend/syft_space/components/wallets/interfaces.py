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

from pydantic import BaseModel


@dataclass
class SetupResult:
    """Result of a wallet setup operation.

    Returned by WalletProvider.setup_wallet().
    """

    credentials: dict[str, Any]
    """Validated credentials to store in Wallet.configuration."""

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
