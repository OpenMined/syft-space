// Single source of truth for the Xendit currency-country pairing on the
// frontend. Mirrors backend CURRENCY_TO_COUNTRY in
// wallets/gateway/xendit/config.py — keep them in sync.
//
// USD is intentionally absent: cross-border setups (USD against any country)
// are deferred. Each currency is locked to its single home country, and the
// backend rejects mismatched combinations with a 422.

export interface XenditRegion {
  currency: string
  country: string
  countryLabel: string
}

export const XENDIT_REGIONS: readonly XenditRegion[] = [
  { currency: 'IDR', country: 'ID', countryLabel: 'Indonesia' },
  { currency: 'PHP', country: 'PH', countryLabel: 'Philippines' },
  { currency: 'SGD', country: 'SG', countryLabel: 'Singapore' },
  { currency: 'MYR', country: 'MY', countryLabel: 'Malaysia' },
  { currency: 'VND', country: 'VN', countryLabel: 'Vietnam' },
  { currency: 'THB', country: 'TH', countryLabel: 'Thailand' },
] as const

export const XENDIT_CURRENCIES: readonly string[] = XENDIT_REGIONS.map((r) => r.currency)

export function countryForCurrency(currency: string): string {
  return XENDIT_REGIONS.find((r) => r.currency === currency)?.country ?? ''
}
