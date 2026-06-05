"""Stripe wallet configuration.

Houses the wallet-level config schema plus the money-bundle catalog. With
wallet-scoped balances, currency lives here — not on the pricing policy.
Bundles are a static per-currency catalog (see ``PRE_PAID_BALANCE_BUNDLES``).

No country field: the merchant's country is set at the Stripe account
level (implicit in the secret key), not per-wallet. Stripe Checkout
routes payment-method availability based on the customer's location and
the currency at session time, so we don't pre-declare it.

Note on JPY: Stripe treats JPY as a zero-decimal currency (no fractional
units). Bundle amounts in the catalog below are kept as whole numbers;
the boundary converter in ``payments/gateway/stripe/amounts.py`` handles
the unit conversion (see ``STRIPE_ZERO_DECIMAL`` there for the canonical
zero-decimal allowlist).
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class StripeCurrencyCode(StrEnum):
    """Currency codes supported by Syft Space's Stripe integration.

    Strictly a subset of Stripe's full set — adding one requires a matching
    bundle catalog entry below.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    SGD = "SGD"
    AUD = "AUD"
    CAD = "CAD"
    JPY = "JPY"
    BRL = "BRL"


class MoneyBundle(BaseModel):
    """A purchasable money bundle (display name + amount)."""

    name: str = Field(..., description="Display name (e.g., 'Starter', 'Pro')")
    amount: float = Field(..., gt=0, description="Bundle price in the wallet currency")


# Pre-paid balance catalog per currency.
PRE_PAID_BALANCE_BUNDLES: dict[str, list[MoneyBundle]] = {
    StripeCurrencyCode.USD: [
        MoneyBundle(name="Starter", amount=5),
        MoneyBundle(name="Basic", amount=25),
        MoneyBundle(name="Pro", amount=100),
        MoneyBundle(name="Enterprise", amount=500),
    ],
    StripeCurrencyCode.EUR: [
        MoneyBundle(name="Starter", amount=5),
        MoneyBundle(name="Basic", amount=25),
        MoneyBundle(name="Pro", amount=100),
        MoneyBundle(name="Enterprise", amount=500),
    ],
    StripeCurrencyCode.GBP: [
        MoneyBundle(name="Starter", amount=5),
        MoneyBundle(name="Basic", amount=20),
        MoneyBundle(name="Pro", amount=80),
        MoneyBundle(name="Enterprise", amount=400),
    ],
    StripeCurrencyCode.SGD: [
        MoneyBundle(name="Starter", amount=7),
        MoneyBundle(name="Basic", amount=35),
        MoneyBundle(name="Pro", amount=140),
        MoneyBundle(name="Enterprise", amount=700),
    ],
    StripeCurrencyCode.AUD: [
        MoneyBundle(name="Starter", amount=8),
        MoneyBundle(name="Basic", amount=40),
        MoneyBundle(name="Pro", amount=150),
        MoneyBundle(name="Enterprise", amount=750),
    ],
    StripeCurrencyCode.CAD: [
        MoneyBundle(name="Starter", amount=7),
        MoneyBundle(name="Basic", amount=35),
        MoneyBundle(name="Pro", amount=140),
        MoneyBundle(name="Enterprise", amount=700),
    ],
    StripeCurrencyCode.JPY: [
        # Zero-decimal: whole-yen amounts only.
        MoneyBundle(name="Starter", amount=500),
        MoneyBundle(name="Basic", amount=2_500),
        MoneyBundle(name="Pro", amount=10_000),
        MoneyBundle(name="Enterprise", amount=50_000),
    ],
    StripeCurrencyCode.BRL: [
        MoneyBundle(name="Starter", amount=25),
        MoneyBundle(name="Basic", amount=125),
        MoneyBundle(name="Pro", amount=500),
        MoneyBundle(name="Enterprise", amount=2_500),
    ],
}


class StripeWalletConfig(BaseModel):
    """Stripe wallet credentials and money-balance configuration."""

    secret_key: str = Field(
        ...,
        description="Stripe secret API key (sk_test_… for sandbox, sk_live_… for prod)",
    )
    webhook_secret: str = Field(
        ...,
        description=(
            "Stripe webhook endpoint signing secret (whsec_…). Each webhook "
            "endpoint registered in the Stripe Dashboard has its own secret."
        ),
    )
    currency: StripeCurrencyCode = Field(..., description="Wallet currency")

    @property
    def prepaid_balance_bundles(self) -> list[MoneyBundle]:
        """Return pre-paid balance bundles for the currency."""
        return PRE_PAID_BALANCE_BUNDLES.get(self.currency, [])

    def get_bundle(self, bundle_name: str) -> MoneyBundle | None:
        """Find a bundle by name, or None if not found."""
        return next(
            (b for b in self.prepaid_balance_bundles if b.name == bundle_name), None
        )
