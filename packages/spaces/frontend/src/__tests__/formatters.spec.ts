import { describe, expect, it } from 'vitest'
import { formatCompactNumber, formatCurrency, formatPrice } from '@/lib/formatters'

describe('formatCompactNumber', () => {
  it('returns raw number below 1000', () => {
    expect(formatCompactNumber(0)).toBe('0')
    expect(formatCompactNumber(42)).toBe('42')
    expect(formatCompactNumber(999)).toBe('999')
  })

  it('formats thousands with k suffix', () => {
    expect(formatCompactNumber(1_000)).toBe('1.0k')
    expect(formatCompactNumber(1_500)).toBe('1.5k')
    expect(formatCompactNumber(127_400)).toBe('127.4k')
    expect(formatCompactNumber(999_999)).toBe('1000.0k')
  })

  it('formats millions with M suffix', () => {
    expect(formatCompactNumber(1_000_000)).toBe('1.0M')
    expect(formatCompactNumber(2_500_000)).toBe('2.5M')
    expect(formatCompactNumber(100_000_000)).toBe('100.0M')
  })
})

describe('formatCurrency', () => {
  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('formats small amounts with 2 decimals', () => {
    expect(formatCurrency(1.5)).toBe('$1.50')
    expect(formatCurrency(0.1)).toBe('$0.10')
  })

  it('formats large amounts with commas', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56')
    expect(formatCurrency(1_000_000)).toBe('$1,000,000.00')
  })

  it('rounds to 2 decimal places', () => {
    expect(formatCurrency(1.999)).toBe('$2.00')
    expect(formatCurrency(1.004)).toBe('$1.00')
  })
})

describe('formatPrice', () => {
  it('adds .00 to integers', () => {
    expect(formatPrice(5)).toBe('5.00')
  })

  it('pads to 2 decimals', () => {
    expect(formatPrice(5.1)).toBe('5.10')
  })

  it('keeps 2 decimals as-is', () => {
    expect(formatPrice(5.12)).toBe('5.12')
  })

  it('preserves extra decimals for microtransactions', () => {
    expect(formatPrice(0.001)).toBe('0.001')
    expect(formatPrice(0.0001)).toBe('0.0001')
  })
})
