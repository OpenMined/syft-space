import type { BenchmarkTarget } from '@/api/types'

/** What every figure shows when it cannot be computed. */
export const DASH = '—'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** A share as a whole percent: 0.8 → `80%`. */
export function pct(x: number | null | undefined): string {
  return typeof x === 'number' ? `${Math.round(x * 100)}%` : DASH
}

/** part / whole; null when there is nothing to divide by. */
export function rate(part: number, whole: number): number | null {
  return whole > 0 ? part / whole : null
}

/** Points, signed and rounded: 50 → `+50`. */
export function points(x: number | null | undefined): string {
  if (typeof x !== 'number') return DASH
  const n = Math.round(x)
  if (n > 0) return `+${n}`
  return n < 0 ? `−${-n}` : '0'
}

/** A lift range in points: `+47 to +70`, or one figure when both ends agree. */
export function pointsRange(lo: number | null, hi: number | null): string {
  if (lo === null || hi === null) return DASH
  const a = points(lo)
  const b = points(hi)
  return a === b ? a : `${a} to ${b}`
}

export function count(x: number | null | undefined): string {
  return typeof x === 'number' ? x.toLocaleString('en') : DASH
}

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.valueOf()) ? null : d
}

const two = (n: number) => String(n).padStart(2, '0')

/** `30 Sep 2026`, in the reader's time zone. */
export function day(iso: string | null | undefined): string | null {
  const d = parse(iso)
  return d ? `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` : null
}

/** `30 Sep 2026, 06:00`, in the reader's time zone. */
export function dayTime(iso: string | null | undefined): string {
  const d = parse(iso)
  if (!d) return DASH
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${two(d.getHours())}:${two(d.getMinutes())}`
}

/** The reader's calendar day of a stamp, `YYYY-MM-DD`, as a date input holds it. */
export function localDay(iso: string | null | undefined): string | null {
  const d = parse(iso)
  return d ? `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}` : null
}

function windowWords(days: number): string {
  return days === 1 ? '24 hours' : `${days} days`
}

/** `articles from the previous 24 hours`; null for a whole-corpus or unknown window. */
export function windowText(days: number | null | undefined): string | null {
  return typeof days === 'number' && days > 0
    ? `articles from the previous ${windowWords(days)}`
    : null
}

function cadence(target: BenchmarkTarget): string | null {
  const m = /^(\d+)h$/.exec(target.schedule)
  if (!m) return null
  const hours = Number(m[1])
  if (hours === 24) {
    const next = parse(target.next_run_at)
    const at = next ? `${two(next.getHours())}:${two(next.getMinutes())}` : target.schedule_at
    return at ? `One run a day at ${at}` : 'One run a day'
  }
  return hours === 1 ? 'One run every hour' : `One run every ${hours} hours`
}

/** The schedule in one line, or null when nothing runs on a schedule. */
export function scheduleText(target: BenchmarkTarget | null | undefined): string | null {
  if (!target) return null
  const head = cadence(target)
  if (!head) return null
  const days = target.probe?.document_window_days
  const scope =
    typeof days === 'number' && days > 0
      ? `, on the articles you published in the previous ${windowWords(days)}`
      : ''
  const next = target.next_run_at ? ` Next run: ${dayTime(target.next_run_at)}.` : ''
  return `${head}${scope}.${next}`
}
