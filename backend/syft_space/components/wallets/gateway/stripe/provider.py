"""Stripe wallet provider — adapter for Stripe payment gateway wallets.

Stripe wallets store the merchant's secret API key (``sk_…``) plus the
webhook endpoint signing secret (``whsec_…``) the merchant retrieves from
their Stripe Dashboard after registering a webhook endpoint pointed at our
public URL.

Setup UX (v1, manual):
1. User creates a Stripe wallet via /wallets/gateway/stripe.
2. Backend returns a wallet-id-stamped webhook URL in display.webhook_url.
3. User pastes that URL into Stripe Dashboard → Developers → Webhooks →
   Add endpoint, with events:
     - checkout.session.completed
     - checkout.session.expired
     - checkout.session.async_payment_succeeded
     - checkout.session.async_payment_failed
4. User copies the revealed ``whsec_…`` and pastes it into our webhook
   secret field (PATCH update credentials).

This mirrors the Xendit "paste the callback token" flow. A future
enhancement could programmatically register the webhook via Stripe's
POST /v1/webhook_endpoints, but that requires the secret key at setup
time to have ``webhook_endpoint:write`` and couples our lifecycle to
theirs — defer until we see demand.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from syft_space.components.wallets.gateway.stripe.config import StripeWalletConfig
from syft_space.components.wallets.interfaces import SetupResult
from syft_space.config import app_settings


class StripeWalletProvider:
    """Adapter for Stripe payment gateway wallets."""

    NAME = "stripe"

    @property
    def config_class(self) -> type[BaseModel]:
        return StripeWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        """Validate Stripe credentials and surface currency to the entity.

        The wallet-id-stamped webhook URL can't be computed here because
        we don't have the wallet id yet — it's filled in by
        ``extract_display`` once the wallet row is committed, and the
        WalletHandler patches it onto the response.
        """
        validated = StripeWalletConfig(**raw_credentials)
        return SetupResult(
            credentials=validated.model_dump(),
            currency=validated.currency,
            country=None,  # Stripe has no per-wallet country lock
            display={},
        )

    def extract_display(
        self, configuration: dict[str, Any], wallet_id: UUID
    ) -> dict[str, Any]:
        """Return the wallet-scoped webhook URL.

        Never exposes ``secret_key`` or ``webhook_secret``. The wallet_id is
        part of the URL path so the route can look up the wallet's signing
        secret before parsing the (untrusted) webhook body — Stripe's HMAC
        scheme requires the body bytes to be unmodified, so we cannot read
        the body to discover which wallet to verify against.
        """
        base = str(app_settings.public_url).rstrip("/")
        webhook_url = f"{base}/api/v1/payments/gateway/stripe/webhooks/{wallet_id}"
        return {"webhook_url": webhook_url}

    # Fields editable post-creation. Currency is locked at the entity level
    # (changing it would re-denominate existing UserBalance / LedgerEntry
    # rows). secret_key + webhook_secret are rotatable since they don't
    # affect ledger invariants. Bundles are also editable but stay static
    # per currency in v1 — slot reserved for tenant-configurable bundles.
    _UPDATABLE_FIELDS = frozenset({"secret_key", "webhook_secret", "bundles"})

    def update_credentials(
        self,
        current_config: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update Stripe wallet config; currency is immutable post-creation."""
        invalid = set(updates.keys()) - self._UPDATABLE_FIELDS
        if invalid:
            raise ValueError(
                f"Cannot update fields: {sorted(invalid)}. "
                f"Allowed: {sorted(self._UPDATABLE_FIELDS)}. "
                "Currency is locked once the wallet exists."
            )
        config = StripeWalletConfig(**current_config)
        updated = config.model_copy(update=updates)
        return updated.model_dump()
