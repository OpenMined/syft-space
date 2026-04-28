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
    WEBHOOK_PATH = "api/v1/payments/gateway/xendit/webhooks"

    @property
    def config_class(self) -> type[BaseModel]:
        return XenditWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        """Pass through Xendit credentials.

        No generation or transformation needed — user provides everything.
        Validation happens in the handler via config_class().
        """

        base = str(app_settings.public_url).rstrip("/")
        webhook_url = f"{base}/{self.WEBHOOK_PATH}"

        return SetupResult(
            credentials=raw_credentials,
            display={"webhook_url": webhook_url},
        )

    def extract_display(self, configuration: dict[str, Any]) -> dict[str, Any]:
        """Return webhook URL — never expose api_key or callback_token."""
        base = str(app_settings.public_url).rstrip("/")
        webhook_url = f"{base}/{self.WEBHOOK_PATH}"
        return {"webhook_url": webhook_url}

    def update_credentials(
        self,
        current_config: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update Xendit credentials (api_key and/or callback_token)."""
        allowed = XenditWalletConfig.model_fields.keys()
        invalid = set(updates.keys()) - allowed
        if invalid:
            raise ValueError(
                f"Cannot update fields: {sorted(invalid)}. Allowed: {sorted(allowed)}"
            )
        config = XenditWalletConfig(**current_config)
        updated = config.model_copy(update=updates)
        return updated.model_dump()
