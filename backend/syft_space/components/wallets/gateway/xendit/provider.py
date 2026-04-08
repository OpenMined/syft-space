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
from syft_space.config import app_settings


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

        webhook_url = (
            f"{app_settings.public_url}/api/v1/payments/gateway/xendit/webhooks"
        )

        return SetupResult(
            credentials=raw_credentials,
            display={"webhook_url": webhook_url},
        )

    def extract_display(self, configuration: dict[str, Any]) -> dict[str, Any]:
        """Return webhook URL — never expose api_key or callback_token."""
        webhook_url = (
            f"{app_settings.public_url}/api/v1/payments/gateway/xendit/webhooks"
        )
        return {"webhook_url": webhook_url}

    def update_credentials(
        self,
        current_config: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Xendit credentials are replaced entirely, not partially updated."""
        raise ValueError(
            "Xendit wallets do not support partial updates. Delete and recreate."
        )
