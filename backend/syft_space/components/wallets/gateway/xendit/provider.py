"""Xendit wallet provider — adapter for Xendit payment gateway wallets.

This is an interface adapter (outer layer) that implements the
WalletProvider Protocol. Xendit wallets store API credentials
provided by the user — no key generation needed.

Validation is handled by the config class (XenditWalletConfig) in
the handler, not here. The provider only transforms/enriches.
"""

from typing import Any

from pydantic import BaseModel

from syft_space.components.wallets.gateway.xendit.config import XenditWalletConfig
from syft_space.components.wallets.interfaces import SetupResult


class XenditWalletProvider:
    """Adapter for Xendit payment gateway wallets."""

    NAME = "xendit"

    @property
    def config_class(self) -> type[BaseModel]:
        return XenditWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        """Pass through Xendit credentials.

        No generation or transformation needed — user provides everything.
        Validation happens in the handler via config_class().
        """
        return SetupResult(
            credentials=raw_credentials,
            display={},
        )
