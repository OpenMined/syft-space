"""Xendit wallet configuration.

Houses the wallet-level config schema plus the money-bundle catalog.
With wallet-scoped balances, currency lives here — not on the pricing
policy. Bundles are a static per-currency catalog (see
PRE_PAID_BALANCE_BUNDLES).
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class CountryCode(StrEnum):
    """Country codes supported by Xendit."""

    ID = "ID"
    PH = "PH"
    SG = "SG"
    MY = "MY"
    VN = "VN"
    TH = "TH"


class CurrencyCode(StrEnum):
    """Currency codes supported by Xendit."""

    IDR = "IDR"
    USD = "USD"
    PHP = "PHP"
    SGD = "SGD"
    MYR = "MYR"
    VND = "VND"
    THB = "THB"


class MoneyBundle(BaseModel):
    """A purchasable money bundle (display name + amount)."""

    name: str = Field(..., description="Display name (e.g., 'Starter', 'Pro')")
    amount: float = Field(..., gt=0, description="Bundle price in the wallet currency")


# Pre-paid balance catalog per currency. Admins cannot override — bundles
# are derived from the wallet's currency.
PRE_PAID_BALANCE_BUNDLES: dict[str, list[MoneyBundle]] = {
    CurrencyCode.IDR: [
        MoneyBundle(name="Starter", amount=10_000),
        MoneyBundle(name="Basic", amount=50_000),
        MoneyBundle(name="Pro", amount=100_000),
        MoneyBundle(name="Enterprise", amount=500_000),
    ],
    CurrencyCode.USD: [
        MoneyBundle(name="Starter", amount=1),
        MoneyBundle(name="Basic", amount=5),
        MoneyBundle(name="Pro", amount=10),
        MoneyBundle(name="Enterprise", amount=50),
    ],
    CurrencyCode.PHP: [
        MoneyBundle(name="Starter", amount=100),
        MoneyBundle(name="Basic", amount=500),
        MoneyBundle(name="Pro", amount=1_000),
        MoneyBundle(name="Enterprise", amount=5_000),
    ],
    CurrencyCode.SGD: [
        MoneyBundle(name="Starter", amount=1),
        MoneyBundle(name="Basic", amount=5),
        MoneyBundle(name="Pro", amount=10),
        MoneyBundle(name="Enterprise", amount=50),
    ],
    CurrencyCode.MYR: [
        MoneyBundle(name="Starter", amount=5),
        MoneyBundle(name="Basic", amount=20),
        MoneyBundle(name="Pro", amount=50),
        MoneyBundle(name="Enterprise", amount=200),
    ],
    CurrencyCode.VND: [
        MoneyBundle(name="Starter", amount=25_000),
        MoneyBundle(name="Basic", amount=100_000),
        MoneyBundle(name="Pro", amount=250_000),
        MoneyBundle(name="Enterprise", amount=1_000_000),
    ],
    CurrencyCode.THB: [
        MoneyBundle(name="Starter", amount=35),
        MoneyBundle(name="Basic", amount=150),
        MoneyBundle(name="Pro", amount=350),
        MoneyBundle(name="Enterprise", amount=1_500),
    ],
}


class XenditWalletConfig(BaseModel):
    """Xendit wallet credentials and money-balance configuration."""

    api_key: str = Field(..., description="Xendit API key")
    callback_token: str = Field(
        ..., description="Xendit webhook callback verification token"
    )
    currency: CurrencyCode = Field(..., description="Wallet currency")
    country: CountryCode = Field(..., description="Country code for Xendit API")

    @property
    def prepaid_balance_bundles(self) -> list[MoneyBundle]:
        """Return pre-paid balance bundles for the currency."""
        return PRE_PAID_BALANCE_BUNDLES.get(self.currency, [])

    def get_bundle(self, bundle_name: str) -> MoneyBundle | None:
        """Find a bundle by name, or None if not found."""
        return next(
            (b for b in self.prepaid_balance_bundles if b.name == bundle_name), None
        )
