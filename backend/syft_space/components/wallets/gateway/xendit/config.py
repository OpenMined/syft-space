"""Xendit wallet configuration.

Houses the wallet-level config schema plus the money-bundle catalog.
With wallet-scoped balances, currency lives here — not on the pricing
policy. Bundles are a static per-currency catalog (see
PRE_PAID_BALANCE_BUNDLES).
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CountryCode(StrEnum):
    """Country codes supported by Xendit."""

    ID = "ID"
    PH = "PH"
    SG = "SG"
    MY = "MY"
    VN = "VN"
    TH = "TH"


class CurrencyCode(StrEnum):
    """Currency codes supported by Xendit.

    USD is intentionally absent — cross-border (USD against any country) is
    deferred. Each currency is locked to its single home country via
    CURRENCY_TO_COUNTRY below, so mismatched combinations fail validation.
    """

    IDR = "IDR"
    PHP = "PHP"
    SGD = "SGD"
    MYR = "MYR"
    VND = "VND"
    THB = "THB"


# Single source of truth for currency-country pairing. Xendit channel
# availability is filtered by country, so picking a country that doesn't
# match the local currency leaves only multi-country channels (e.g. cards)
# available — confusing for merchants and the cause of the "No available
# channels" Xendit error we hit when an SGD wallet shipped with country=ID.
CURRENCY_TO_COUNTRY: dict[CurrencyCode, CountryCode] = {
    CurrencyCode.IDR: CountryCode.ID,
    CurrencyCode.PHP: CountryCode.PH,
    CurrencyCode.SGD: CountryCode.SG,
    CurrencyCode.MYR: CountryCode.MY,
    CurrencyCode.VND: CountryCode.VN,
    CurrencyCode.THB: CountryCode.TH,
}


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

    @model_validator(mode="after")
    def _check_currency_country_pairing(self) -> "XenditWalletConfig":
        expected = CURRENCY_TO_COUNTRY.get(self.currency)
        if expected is not None and self.country != expected:
            raise ValueError(
                f"Currency {self.currency.value} must be paired with country "
                f"{expected.value}, got {self.country.value}. Cross-border "
                f"pairings are not yet supported."
            )
        return self

    @property
    def prepaid_balance_bundles(self) -> list[MoneyBundle]:
        """Return pre-paid balance bundles for the currency."""
        return PRE_PAID_BALANCE_BUNDLES.get(self.currency, [])

    def get_bundle(self, bundle_name: str) -> MoneyBundle | None:
        """Find a bundle by name, or None if not found."""
        return next(
            (b for b in self.prepaid_balance_bundles if b.name == bundle_name), None
        )
