"""Stripe amount-unit conversion.

Stripe expects integer amounts in the smallest currency unit:
- Two-decimal currencies (USD, EUR, …): cents. $10.00 → 1000.
- Zero-decimal currencies (JPY, KRW, …): whole units. ¥500 → 500.

Internally the codebase stores money as float-in-major-units across both
providers; only the Stripe API boundary needs to convert. We keep this
conversion strictly local: webhooks for accounting carry our own invoice
amount via ``client_reference_id`` lookup, so we never need to convert
back from Stripe's minor units for credit/debit math.

The full Stripe-side zero-decimal list is broader than what Syft Space
currently exposes; we keep an explicit allowlist for our supported
currencies and grow it deliberately when adding new ones to
``StripeCurrencyCode``. Drifting silently is dangerous — a missed
zero-decimal currency would charge 100× the intended amount.
"""

STRIPE_ZERO_DECIMAL: frozenset[str] = frozenset(
    {
        # The launch set
        "JPY",
        # Add others here as ``StripeCurrencyCode`` grows. Reference:
        # https://docs.stripe.com/currencies#zero-decimal
        # "BIF","CLP","DJF","GNF","KMF","KRW","MGA","PYG","RWF",
        # "UGX","VND","VUV","XAF","XOF","XPF",
    }
)


def to_stripe_minor_units(amount: float, currency: str) -> int:
    """Convert a major-unit float to Stripe's integer minor-unit format.

    Rounds to the nearest integer (banker's rounding via Python's ``round``).
    Bundles in our catalog are integers-in-major-units (Xendit, Stripe)
    so rounding only matters defensively; if a future bundle adds cents,
    the math stays correct.
    """
    if currency.upper() in STRIPE_ZERO_DECIMAL:
        return int(round(amount))
    return int(round(amount * 100))
