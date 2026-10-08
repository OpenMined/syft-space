/** Where a job's time went, in words for the technical view. */
import type { BenchmarkRunTiming } from '@/api/types'

const PHASES: Record<string, string> = {
  generate: 'Generate',
  filter: 'Filter',
  evaluate: 'Evaluate',
  judge: 'Judge',
  publish: 'Publish',
}

export function phaseLabel(phase: string): string {
  return PHASES[phase] ?? phase.charAt(0).toUpperCase() + phase.slice(1)
}

const ROLES: Record<string, string> = { answer: 'Tested', judge: 'Judge' }

export function roleLabel(role: string): string {
  return ROLES[role] ?? role
}

/** `0.42s`, `8.3s`, `12m 5s`, `1h 52m`. */
export function duration(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return '—'
  if (seconds < 1) return `${seconds.toFixed(2)}s`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const whole = Math.round(seconds)
  if (whole < 3600) return `${Math.floor(whole / 60)}m ${whole % 60}s`
  const minutes = Math.round(whole / 60)
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

/** Seconds between two ISO timestamps; null when either is missing or out of order. */
export function runSpan(from: string | null | undefined, to: string | null | undefined): number | null {
  if (!from || !to) return null
  const s = (Date.parse(to) - Date.parse(from)) / 1000
  return Number.isFinite(s) && s >= 0 ? s : null
}

/** Whether there is anything to show. */
export function hasTiming(t: BenchmarkRunTiming | null | undefined): t is BenchmarkRunTiming {
  return !!t && (t.total_s > 0 || !!t.phases?.length || !!t.passes?.length || !!t.calls?.length)
}
