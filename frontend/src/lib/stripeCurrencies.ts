// Frontend mirror of the Stripe wallet launch currency set. Keep in sync
// with backend/syft_space/components/wallets/gateway/stripe/config.py:
// StripeCurrencyCode + PRE_PAID_BALANCE_BUNDLES.
//
// Stripe accepts 135+ currencies, but we only expose the ones with a
// curated bundle catalog. No country pairing (unlike Xendit) — Stripe
// figures payment methods out per-account in the Dashboard.

export interface StripeCurrencyOption {
  currency: string
  label: string
}

export const STRIPE_CURRENCIES: readonly StripeCurrencyOption[] = [
  { currency: 'USD', label: 'US Dollar' },
  { currency: 'EUR', label: 'Euro' },
  { currency: 'GBP', label: 'British Pound' },
  { currency: 'SGD', label: 'Singapore Dollar' },
  { currency: 'AUD', label: 'Australian Dollar' },
  { currency: 'CAD', label: 'Canadian Dollar' },
  { currency: 'JPY', label: 'Japanese Yen' },
  { currency: 'BRL', label: 'Brazilian Real' },
] as const
