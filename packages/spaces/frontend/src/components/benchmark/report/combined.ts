/** Labels for combined runs: badges, names and setting values. */
import type { BenchmarkCombinedInfo, BenchmarkCombinedRef, BenchmarkRunSummary } from '@/api/types'
import { plural } from '../labels'
import { DASH, dayTime, utcStamp } from './figures'

/** The badge of a combined run: `Combined` by hand, the period when automatic. */
export function combinedBadge(info: BenchmarkCombinedInfo): string {
  return info.origin === 'auto' && info.period ? info.period : 'Combined'
}

export function combinedTip(info: BenchmarkCombinedInfo): string {
  return `Combines ${plural(info.members, 'run', 'runs')}.`
}

/** A run's name: its title, else when it was made. */
export function runName(run: Pick<BenchmarkRunSummary, 'created_at' | 'combined'>): string {
  return run.combined?.title || dayTime(utcStamp(run.created_at))
}

/** A run report's heading: a combined run's title, else when the run was made. */
export function runHeading(run: Pick<BenchmarkRunSummary, 'created_at' | 'combined'>): string {
  if (run.combined?.title) return run.combined.title
  const made = dayTime(utcStamp(run.created_at))
  return run.combined ? `Combined run of ${made}` : `Run of ${made}`
}

/** A listed run's name by its job id; the id's start when it is not listed. */
export function runNameById(jobId: string, runs: readonly BenchmarkRunSummary[]): string {
  const found = runs.find((r) => r.job_id === jobId)
  return found ? runName(found) : jobId.slice(0, 8)
}

/** The tooltip of a run a combined run holds, naming the combined runs. */
export function heldTip(
  held: readonly BenchmarkCombinedRef[],
  runs: readonly BenchmarkRunSummary[],
): string {
  const names = held.map((c) => `“${c.title || runNameById(c.job_id, runs)}”`).join(', ')
  return `Part of the combined ${held.length === 1 ? 'run' : 'runs'} ${names}.`
}

const TRIGGER: Record<string, string> = {
  manual: 'By hand',
  schedule: 'Scheduled',
}

export function triggerLabel(trigger: string): string {
  return TRIGGER[trigger] ?? trigger
}

/** A setting's value as one short line. */
export function settingValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return DASH
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}
