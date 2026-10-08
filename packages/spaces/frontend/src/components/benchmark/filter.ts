/** Pure helpers for a job's generation stats and filter decisions. */
import type {
  BenchmarkBuildCounts,
  BenchmarkFilterDecision,
  BenchmarkFilterOutcome,
  BenchmarkKindBuild,
  BenchmarkWebCheck,
} from '@/api/types'
import { day } from './report/figures'
import { REMOVED_REASON_LABEL, removedReasonLabel } from './report/labels'
import { utcStamp } from './report/selectors'

export const OUTCOMES: BenchmarkFilterOutcome[] = ['kept', 'removed', 'failed', 'skipped']

const OUTCOME_LABEL: Record<BenchmarkFilterOutcome, string> = {
  kept: 'Kept',
  removed: 'Removed',
  failed: 'Failed',
  skipped: 'Skipped',
}

const OUTCOME_TONE: Record<BenchmarkFilterOutcome, string> = {
  kept: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  removed: 'bg-destructive/10 text-destructive',
  failed: 'bg-warning/20 text-foreground',
  skipped: 'bg-muted text-muted-foreground',
}

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABEL[outcome as BenchmarkFilterOutcome] ?? outcome
}

export function outcomeTone(outcome: string): string {
  return OUTCOME_TONE[outcome as BenchmarkFilterOutcome] ?? OUTCOME_TONE.skipped
}

const STAGE_LABEL: Record<string, string> = {
  grounding: 'Grounding',
  control: 'Search',
  web_check: 'Web check',
}

export function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage
}

/** The reason in words: a known code's label, then the server's note when it says more. */
export function reasonText(d: Pick<BenchmarkFilterDecision, 'reason' | 'reason_code'>): string {
  const note = (d.reason ?? '').trim()
  const isCode = note in REMOVED_REASON_LABEL
  const code = d.reason_code && d.reason_code !== 'other' ? d.reason_code : isCode ? note : null
  if (!code) return note
  const label = removedReasonLabel(code)
  return note && !isCode ? `${label}: ${note}` : label
}

/** `Written in 30 Sep 2026` for a question an earlier job wrote; null otherwise. */
export function writtenInText(
  d: Pick<BenchmarkFilterDecision, 'earlier' | 'written_by_job_at' | 'written_at'>,
): string | null {
  if (!d.earlier) return null
  const when = day(utcStamp(d.written_by_job_at ?? d.written_at))
  return when ? `Written in ${when}` : 'Written earlier'
}

/** Whether the row has web check details to unfold. */
export function hasDetails(w: BenchmarkWebCheck | null | undefined): w is BenchmarkWebCheck {
  if (!w) return false
  return Boolean(
    w.answer || w.verdict || w.reasoning || w.citations?.length || w.searches || w.error,
  )
}

/** `3 kept · 2 removed`, outcomes with zero left out. */
export function countsText(counts: Partial<Record<BenchmarkFilterOutcome, number>>): string {
  return OUTCOMES.filter((o) => (counts[o] ?? 0) > 0)
    .map((o) => `${counts[o]} ${OUTCOME_LABEL[o].toLowerCase()}`)
    .join(' · ')
}

/** `12 written · 4 removed` for a job that asked no model. */
export function buildText(build: BenchmarkBuildCounts | null | undefined): string | null {
  if (!build) return null
  const parts = [`${build.written} written`]
  if (build.removed) parts.push(`${build.removed} removed`)
  if (build.failed) parts.push(`${build.failed} failed`)
  return parts.join(' · ')
}

export function safeUrl(url: string): string | undefined {
  return /^https?:\/\//i.test(url) ? url : undefined
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

const STOPPED_LABEL: Record<string, string> = {
  'budget reached': 'Budget reached',
  'ran out of material': 'Out of material',
  'failure streak': 'Failures',
  cancelled: 'Cancelled',
}

/** Why a kind stopped writing, as a 1-2 word chip. */
export function stoppedLabel(stopped: string): string {
  return STOPPED_LABEL[stopped] ?? stopped.charAt(0).toUpperCase() + stopped.slice(1)
}

export function droppedTotal(kind: Pick<BenchmarkKindBuild, 'dropped'>): number {
  return Object.values(kind.dropped ?? {}).reduce((sum, n) => sum + n, 0)
}

/** Drop reasons, largest first: `duplicate: 3`. */
export function droppedLines(kind: Pick<BenchmarkKindBuild, 'dropped'>): string[] {
  return Object.entries(kind.dropped ?? {})
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([reason, n]) => `${reason}: ${n}`)
}

/** `12 / 40 passages`, failed reads noted. */
export function readText(
  kind: Pick<BenchmarkKindBuild, 'unit' | 'units_read' | 'units_available' | 'failed_units'>,
): string {
  const unit = kind.unit === 'article' ? 'articles' : 'passages'
  const failed = kind.failed_units ? `, ${kind.failed_units} failed` : ''
  return `${kind.units_read} / ${kind.units_available} ${unit}${failed}`
}
