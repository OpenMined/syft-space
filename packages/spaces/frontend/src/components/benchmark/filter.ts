/** Pure helpers for a job's generation stats and filter decisions. */
import type {
  BenchmarkBuildCounts,
  BenchmarkFilterDecision,
  BenchmarkFilterOutcome,
  BenchmarkKindBuild,
} from '@/api/types'
import { TONE } from './labels'
import { REMOVED_REASON_LABEL, removedReasonLabel } from './report/labels'

const OUTCOME_LABEL: Record<BenchmarkFilterOutcome, string> = {
  kept: 'Kept',
  removed: 'Removed',
  failed: 'Failed',
}

const OUTCOME_TONE: Record<BenchmarkFilterOutcome, string> = {
  kept: TONE.good,
  removed: TONE.bad,
  failed: TONE.failed,
}

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABEL[outcome as BenchmarkFilterOutcome] ?? outcome
}

export function outcomeTone(outcome: string): string {
  return OUTCOME_TONE[outcome as BenchmarkFilterOutcome] ?? TONE.muted
}

const STAGE_LABEL: Record<string, string> = {
  writing: 'Writing',
  grounding: 'Grounding',
  control: 'Search',
  web_check: 'Web check',
}

export function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage
}

/** The reason in words: a known code's label, then the server's note when it says more. */
export function reasonText(d: Pick<BenchmarkFilterDecision, 'reason' | 'reason_code'>): string {
  let note = (d.reason ?? '').trim()
  const isCode = note in REMOVED_REASON_LABEL
  const code = d.reason_code && d.reason_code !== 'other' ? d.reason_code : isCode ? note : null
  if (!code) return note
  const label = removedReasonLabel(code)
  // Drop a repeated code prefix, e.g. `ambiguous entity: Mariam`.
  const lead = `${code.replace(/_/g, ' ')}:`
  if (note.toLowerCase().startsWith(lead)) note = note.slice(lead.length).trim()
  const repeats = note.toLowerCase() === label.toLowerCase()
  return note && !isCode && !repeats ? `${label}: ${note}` : label
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
  'top-up cost limit': 'Cost limit',
}

export type KindBuildStat = 'written' | 'read' | 'dropped' | 'stopped'

/** The figures of a kind's writing, with the hint over each heading. */
export const KIND_BUILD_STATS: { key: KindBuildStat; label: string; tip: string | null }[] = [
  { key: 'written', label: 'Written', tip: 'Of the budget, top-ups included.' },
  { key: 'read', label: 'Read', tip: 'Passages or articles read, of those available.' },
  { key: 'dropped', label: 'Dropped', tip: 'Thrown away while writing; hover a number for reasons.' },
  { key: 'stopped', label: 'Stopped', tip: null },
]

/** Why a kind stopped writing, as a 1-2 word chip. */
export function kindStoppedLabel(stopped: string): string {
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

/** `12 / 10`, top-up writes noted. */
export function writtenText(
  kind: Pick<BenchmarkKindBuild, 'written' | 'budget' | 'topped_up'>,
): string {
  const extra = kind.topped_up ? `, ${kind.topped_up} topped up` : ''
  return `${kind.written} / ${kind.budget}${extra}`
}

/** `12 / 40 passages`, failed reads noted. */
export function readText(
  kind: Pick<BenchmarkKindBuild, 'unit' | 'units_read' | 'units_available' | 'failed_units'>,
): string {
  const unit = kind.unit === 'article' ? 'articles' : 'passages'
  const failed = kind.failed_units ? `, ${kind.failed_units} failed` : ''
  return `${kind.units_read} / ${kind.units_available} ${unit}${failed}`
}
