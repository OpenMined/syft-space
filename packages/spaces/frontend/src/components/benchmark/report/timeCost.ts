/** A run's time and cost in words. */
import type { BenchmarkCostByRole, BenchmarkRunReport, BenchmarkRunSummary } from '@/api/types'
import { runSpan } from '../timing'
import { clock, shortStamp, utcStamp } from './figures'

/** Seconds from job start to finish; null for older runs or a run still going. */
export function runDuration(
  run: Pick<BenchmarkRunSummary, 'started_at' | 'finished_at'>,
): number | null {
  return runSpan(utcStamp(run.started_at), utcStamp(run.finished_at))
}

/** `54 min`, `1 h 52 min`, `<1 min`. */
export function tookText(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes < 1) return '<1 min'
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

/** `Started 06:00 · finished 06:54`, local time; the finish gets its day when it differs. */
export function startFinishText(
  run: Pick<BenchmarkRunSummary, 'started_at' | 'finished_at'>,
): string | null {
  const from = utcStamp(run.started_at)
  const to = utcStamp(run.finished_at)
  if (!from || !to) return null
  const a = new Date(from)
  const b = new Date(to)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null
  const sameDay = a.toDateString() === b.toDateString()
  return `Started ${clock(a)} · finished ${sameDay ? clock(b) : shortStamp(to)}`
}

/** Shown to the customer: the per-call sum, else the key-spend delta. */
export function customerCost(method: BenchmarkRunReport['method']): number | null {
  const cost = method.cost
  if (!cost) return null
  if (typeof cost.total_usd === 'number') return cost.total_usd
  if (cost.usd_calls > 0) return cost.usd_calls
  return typeof cost.usd === 'number' ? cost.usd : null
}

/** OpenRouter key spend during the run (technical view); null when unread. */
export function keySpend(method: BenchmarkRunReport['method']): number | null {
  const usd = method.cost?.usd
  return typeof usd === 'number' ? usd : null
}

const ROLES: { key: keyof BenchmarkCostByRole; label: string; color: string }[] = [
  { key: 'writer', label: 'Writing questions', color: '#00614F' },
  { key: 'web_check', label: 'Web check', color: '#008574' },
  { key: 'subjects', label: 'Models being tested', color: '#5FB3A6' },
  { key: 'judges', label: 'Judges', color: '#B7DCD6' },
]

export interface CostPart {
  key: keyof BenchmarkCostByRole
  label: string
  color: string
  usd: number
  /** Share of the bar, `31.5%`. */
  width: string
}

/** The four roles in a fixed order; null when the run has no split or spent nothing. */
export function costParts(method: BenchmarkRunReport['method']): CostPart[] | null {
  const by = method.cost?.by_role
  if (!by) return null
  const parts = ROLES.map((r) => ({ ...r, usd: Math.max(Number(by[r.key]) || 0, 0) }))
  const total = parts.reduce((sum, p) => sum + p.usd, 0)
  if (total <= 0) return null
  return parts.map((p) => ({ ...p, width: `${((p.usd / total) * 100).toFixed(1)}%` }))
}

/** The bar's accessible name. */
export function costLabel(parts: CostPart[], usd: (x: number) => string): string {
  return `Cost by role: ${parts.map((p) => `${p.label} ${usd(p.usd)}`).join(', ')}`
}
