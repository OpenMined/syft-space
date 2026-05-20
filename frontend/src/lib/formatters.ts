/**
 * Date and time formatting utilities
 */

export const formatTimestamp = (date: Date): string => {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)

  if (diffHours < 1) {
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    return diffMinutes <= 1 ? 'Just now' : `${diffMinutes} minutes ago`
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  } else {
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }
}

export const formatDate = (date: Date | undefined): string => {
  if (!date) return 'Unknown'

  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export const formatDateShort = (date: Date): string => {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Truncate an email or wallet address for display.
 */
export const truncateEmail = (email: string, maxLocal: number = 6): string => {
  if (email.startsWith('0x') && email.length > 12) {
    return `${email.slice(0, 6)}...${email.slice(-4)}`
  }
  const [local, domain] = email.split('@')
  if (!local || !domain) return email
  const truncatedLocal = local.length > maxLocal ? `${local.slice(0, maxLocal)}...` : local
  return `${truncatedLocal}@${domain}`
}

/**
 * Backend timestamps are UTC, but SQLite-backed datetimes serialize naive
 * (no `Z` / `+00:00`). The Date constructor reads naive ISO strings as
 * *local* time, which shifts every "just now" event by the user's TZ
 * offset. Normalize by appending `Z` when no explicit offset is present.
 */
const parseBackendDate = (dateString: string): Date => {
  const hasTimezone = /Z$|[+-]\d{2}:?\d{2}$/.test(dateString)
  return new Date(hasTimezone ? dateString : `${dateString}Z`)
}

/**
 * Format a date string as a human-readable relative time (in user's local TZ).
 */
export const formatTimeAgo = (dateString: string): string => {
  const date = parseBackendDate(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

/**
 * Format a backend UTC timestamp as a full local-TZ datetime, suitable for
 * tooltips alongside relative times. Example: "May 19, 2026, 6:56:54 PM IST".
 *
 * Uses individual component options (not dateStyle/timeStyle shortcuts) so
 * `timeZoneName` can be combined — Intl rejects mixing the two shortcut
 * options with explicit fields.
 */
export const formatLocalDateTime = (dateString: string): string => {
  return parseBackendDate(dateString).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  })
}

/**
 * Format a number with compact suffix (k, M) for display.
 */
export const formatCompactNumber = (value: number): string => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toLocaleString()
}

/**
 * Format a number as USD currency with 2 decimal places.
 */
export const formatCurrency = (value: number): string => {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// Currencies with no minor unit get whole numbers; everything else gets 2 decimals.
// IDR is included by product convention even though it technically has sen.
const ZERO_DECIMAL_CURRENCIES = new Set(['JPY', 'IDR', 'KRW', 'VND'])

/**
 * Format an amount in any ISO currency using Intl.NumberFormat.
 * Falls back to "<amount> <CODE>" if the runtime can't format the currency code.
 */
export const formatCurrencyAmount = (amount: number, currency: string): string => {
  const code = currency.toUpperCase()
  const fractionDigits = ZERO_DECIMAL_CURRENCIES.has(code) ? 0 : 2
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: code,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(amount)
  } catch {
    return `${amount.toLocaleString('en-US', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    })} ${code}`
  }
}

/**
 * Format a per-currency breakdown for display.
 * Returns the placeholder when the list is empty.
 */
export const formatCurrencyBreakdown = (
  entries: { currency: string; amount: number }[],
  emptyPlaceholder: string = '$0.00',
): string => {
  if (!entries.length) return emptyPlaceholder
  return entries.map((e) => formatCurrencyAmount(e.amount, e.currency)).join(' · ')
}

/**
 * Format a price with minimum 2 decimal places, keeping more if needed for microtransactions.
 * - No decimals → adds .00
 * - ≤2 decimals → formats to 2 decimals
 * - >2 decimals → keeps all decimals
 */
export const formatPrice = (price: number): string => {
  const priceStr = price.toString()
  const decimalIndex = priceStr.indexOf('.')

  if (decimalIndex === -1) {
    return price.toFixed(2)
  }

  const decimalPlaces = priceStr.length - decimalIndex - 1
  if (decimalPlaces <= 2) {
    return price.toFixed(2)
  }

  return priceStr
}
