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
