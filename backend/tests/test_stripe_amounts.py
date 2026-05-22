"""Tests for Stripe amount-unit conversion.

The zero-decimal currency allowlist is load-bearing: missing an entry means
the function multiplies the amount by 100, charging the user 100× the
intended amount. These tests guard against silent drift.
"""

from __future__ import annotations

from syft_space.components.payments.gateway.stripe.amounts import (
    STRIPE_ZERO_DECIMAL,
    to_stripe_minor_units,
)


class TestTwoDecimalCurrencies:
    """Currencies not in STRIPE_ZERO_DECIMAL multiply by 100."""

    def test_usd_whole_amount(self):
        assert to_stripe_minor_units(10.00, "USD") == 1000

    def test_usd_with_cents(self):
        assert to_stripe_minor_units(10.99, "USD") == 1099

    def test_usd_zero(self):
        assert to_stripe_minor_units(0.00, "USD") == 0

    def test_usd_smallest_unit(self):
        assert to_stripe_minor_units(0.01, "USD") == 1

    def test_eur(self):
        assert to_stripe_minor_units(25.50, "EUR") == 2550

    def test_gbp(self):
        assert to_stripe_minor_units(1.23, "GBP") == 123


class TestZeroDecimalCurrencies:
    """Currencies in STRIPE_ZERO_DECIMAL pass through as whole units."""

    def test_jpy_whole_amount(self):
        assert to_stripe_minor_units(500, "JPY") == 500

    def test_jpy_zero(self):
        assert to_stripe_minor_units(0, "JPY") == 0

    def test_jpy_one(self):
        assert to_stripe_minor_units(1, "JPY") == 1

    def test_jpy_large(self):
        assert to_stripe_minor_units(12345, "JPY") == 12345


class TestCaseInsensitivity:
    """Currency code casing must not affect the result."""

    def test_lowercase_zero_decimal(self):
        assert to_stripe_minor_units(500, "jpy") == 500

    def test_mixed_case_zero_decimal(self):
        assert to_stripe_minor_units(500, "Jpy") == 500

    def test_lowercase_two_decimal(self):
        assert to_stripe_minor_units(10.00, "usd") == 1000

    def test_mixed_case_two_decimal(self):
        assert to_stripe_minor_units(10.00, "Usd") == 1000


class TestRounding:
    """Float inputs round to the nearest integer (banker's rounding)."""

    def test_jpy_fractional_rounds_down(self):
        # 500.4 → 500
        assert to_stripe_minor_units(500.4, "JPY") == 500

    def test_jpy_fractional_rounds_up(self):
        # 500.6 → 501
        assert to_stripe_minor_units(500.6, "JPY") == 501

    def test_usd_subcent_rounds_away(self):
        # 10.994 * 100 = 1099.4 → 1099
        assert to_stripe_minor_units(10.994, "USD") == 1099

    def test_usd_subcent_rounds_up(self):
        # 10.996 * 100 = 1099.6 → 1100
        assert to_stripe_minor_units(10.996, "USD") == 1100


class TestAllowlist:
    """STRIPE_ZERO_DECIMAL is the single source of truth for the branch.

    A regression that drops JPY from this set would cause the function to
    return 50000 for a ¥500 invoice — a 100× over-charge. This test fails
    loudly if that ever happens.
    """

    def test_jpy_is_zero_decimal(self):
        assert "JPY" in STRIPE_ZERO_DECIMAL

    def test_usd_is_not_zero_decimal(self):
        assert "USD" not in STRIPE_ZERO_DECIMAL

    def test_eur_is_not_zero_decimal(self):
        assert "EUR" not in STRIPE_ZERO_DECIMAL

    def test_jpy_charges_not_100x(self):
        # The bug we're guarding against: if JPY ever stops being treated
        # as zero-decimal, a ¥500 charge becomes ¥50000.
        assert to_stripe_minor_units(500, "JPY") != 50000
