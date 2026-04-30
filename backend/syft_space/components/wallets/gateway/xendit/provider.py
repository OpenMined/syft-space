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
        """Validate Xendit credentials and surface currency/country to the entity.

        Currency and country are required at wallet-creation time (they live
        on the wallet, not the policy, in the wallet-scoped balance model).
        """

        validated = XenditWalletConfig(**raw_credentials)

        base = str(app_settings.public_url).rstrip("/")
        webhook_url = f"{base}/api/v1/payments/gateway/xendit/webhooks"

        return SetupResult(
            credentials=validated.model_dump(),
            currency=validated.currency,
            country=validated.country,
            display={"webhook_url": webhook_url},
        )

    def extract_display(self, configuration: dict[str, Any]) -> dict[str, Any]:
        """Return webhook URL — never expose api_key or callback_token."""
        base = str(app_settings.public_url).rstrip("/")
        webhook_url = f"{base}/api/v1/payments/gateway/xendit/webhooks"
        return {"webhook_url": webhook_url}

    # Fields editable post-creation. Currency and country are locked at the
    # entity level — they're surfaced as wallet columns and changing them
    # would either break the (tenant, type, currency) uniqueness invariant
    # or re-denominate existing UserBalance / LedgerEntry rows.
    # Bundles are editable since they don't affect ledger invariants.
    _UPDATABLE_FIELDS = frozenset({"api_key", "callback_token", "bundles"})

    def update_credentials(
        self,
        current_config: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update Xendit wallet config; currency and country are immutable post-creation."""
        invalid = set(updates.keys()) - self._UPDATABLE_FIELDS
        if invalid:
            raise ValueError(
                f"Cannot update fields: {sorted(invalid)}. "
                f"Allowed: {sorted(self._UPDATABLE_FIELDS)}. "
                "Currency and country are locked once the wallet exists."
            )
        config = XenditWalletConfig(**current_config)
        updated = config.model_copy(update=updates)
        return updated.model_dump()
