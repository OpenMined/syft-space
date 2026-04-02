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
 * Format a date string as a human-readable relative time.
 */
export const formatTimeAgo = (dateString: string): string => {
  const date = new Date(dateString)
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
