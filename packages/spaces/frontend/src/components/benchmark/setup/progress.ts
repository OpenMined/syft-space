/** The run bar's estimate of the time left and its plan tooltip. */
import type { BenchmarkProgressPlan } from '@/api/types'
import { utcStamp } from '@/components/benchmark/report/selectors'

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** `30 questions × 2 models × 2 conditions × 3 checks`, plus the Monte Carlo skips. */
export function planText(
  plan: BenchmarkProgressPlan | null | undefined,
  nameOf: (id: string) => string = (id) => id,
): string {
  if (!plan) return ''
  const text = [
    plural(plan.questions, 'question'),
    plural(plan.models.length, 'model'),
    plural(plan.conditions.length, 'condition'),
    plural(plan.checks.length, 'check'),
  ].join(' × ')
  const skipped = plan.skipped_monte_carlo ?? []
  return skipped.length ? `${text}. Monte Carlo skipped: ${skipped.map(nameOf).join(', ')}` : text
}

/** Where the pace is measured from: the start of the evaluate phase. */
export function paceStart(plan: BenchmarkProgressPlan | null | undefined): PaceStart | null {
  const iso = utcStamp(plan?.started_at)
  const at = iso ? Date.parse(iso) : NaN
  return Number.isFinite(at) ? { at, done: 0 } : null
}

/** A point the pace is measured from: when it was seen, and the steps done by then. */
export interface PaceStart {
  at: number
  done: number
}

/** Steps and time needed before the pace is trusted. */
const MIN_SHARE = 0.05
const MIN_MS = 60_000

/** Milliseconds left at the pace since `start`; null until enough steps are done. */
export function msLeft(
  done: number,
  total: number,
  start: PaceStart | null,
  now: number,
): number | null {
  if (!start || total <= 0 || done >= total) return null
  const stepped = done - start.done
  const elapsed = now - start.at
  if (elapsed < MIN_MS || stepped <= 0 || stepped < total * MIN_SHARE) return null
  return ((total - done) * elapsed) / stepped
}

/** `About 25 min left`, `About 1 h 10 min left`; empty for no estimate. */
export function leftText(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms) || ms < 0) return ''
  const minutes = Math.max(1, Math.ceil(ms / 60_000))
  if (minutes < 60) return `About ${minutes} min left`
  const rounded = Math.round(minutes / 5) * 5
  const h = Math.floor(rounded / 60)
  const m = rounded % 60
  return m ? `About ${h} h ${m} min left` : `About ${h} h left`
}
