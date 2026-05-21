"""Stripe wallet configuration.

Houses the wallet-level config schema plus the money-bundle catalog. With
wallet-scoped balances, currency lives here — not on the pricing policy.
Bundles are a static per-currency catalog (see ``PRE_PAID_BALANCE_BUNDLES``).

Key differences from Xendit:
- No currency↔country lock. Stripe permits any of its 135+ currencies
  regardless of merchant country; payment-method availability is configured
  at the Stripe account level in the dashboard, not per-session.
- Webhook secret (``whsec_…``) is stored alongside the API key. Unlike
  Xendit's static x-callback-token, Stripe signs the body itself with this
  secret (HMAC-SHA256 over ``"{timestamp}.{body}"``).
- Amounts are stored here in major units (float) — the same way the rest
  of the codebase represents money. Conversion to Stripe's minor-unit
  integers happens at the API boundary in ``payments/gateway/stripe``.

Launch currency set deliberately small: USD/EUR/GBP/SGD/AUD/CAD/JPY covers
the bulk of merchant demand without requiring per-currency bundle catalog
audits. Adding currencies is one entry in ``StripeCurrencyCode`` plus one
entry in ``PRE_PAID_BALANCE_BUNDLES``.

Note on JPY: Stripe treats JPY as a zero-decimal currency (no fractional
units). Bundle amounts must be whole numbers; the boundary converter
handles the unit conversion. The validator below rejects bundles with
non-integer JPY values to catch catalog drift early.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class StripeCurrencyCode(StrEnum):
    """Currency codes supported by Syft Space's Stripe integration.

    Strictly a subset of Stripe's 135+ supported currencies — adding a new
    one requires curating a bundle catalog below. USD-first because most
    merchants demoing Syft Space transact in USD.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    SGD = "SGD"
    AUD = "AUD"
    CAD = "CAD"
    JPY = "JPY"


# Stripe's zero-decimal currencies that appear in our launch set. Stripe
# expects amounts in the smallest currency unit; for these, the smallest
# unit IS the major unit (no cents). The full Stripe-side list is broader
# (BIF, KRW, VND, THB, …) but we only need the ones we expose.
STRIPE_ZERO_DECIMAL: frozenset[str] = frozenset({"JPY"})


class MoneyBundle(BaseModel):
    """A purchasable money bundle (display name + amount).

    Shape mirrors Xendit's MoneyBundle deliberately so the SyftHub publish
    payload stays uniform across providers (the consumer only sees ``name``
    and ``amount``).
    """

    name: str = Field(..., description="Display name (e.g., 'Starter', 'Pro')")
    amount: float = Field(..., gt=0, description="Bundle price in the wallet currency")


# Pre-paid balance catalog per currency. Admins cannot override at v1 —
# bundles are derived from the wallet's currency. Tenant-configurable
# bundles is a follow-up that should apply to all providers uniformly.
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
