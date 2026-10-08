/** Pure helpers that turn the server's report shapes into words. */
import type {
  BenchmarkArmDetail,
  BenchmarkRunProgress,
  BenchmarkRunReport,
  BenchmarkRunSummary,
} from '@/api/types'
import { count, DASH, dayTime } from './figures'
import { KIND_LABEL, modelName } from './labels'
import { TRICK_GENERATOR, type Held, type SettingRow } from './types'

export function isOutcome(verdict: string | null | undefined): boolean {
  return verdict === 'correct' || verdict === 'abstain' || verdict === 'hallucinate'
}

export function isTrick(generator: string | null | undefined): boolean {
  return generator === TRICK_GENERATOR
}

/** A stamp as UTC: the Space stores naive datetimes that are UTC. */
export function utcStamp(value: string | null | undefined): string | null {
  if (!value) return null
  return /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** `30 Sep 06:00`, local time; null for a missing or unreadable stamp. */
export function shortStamp(value: string | null | undefined): string | null {
  const iso = utcStamp(value)
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${hh}:${mm}`
}

/** `Step 11 of 15` for an in-progress run. */
export function progressText(p: BenchmarkRunProgress): string {
  if (p.state === 'queued') return 'Queued'
  return p.step_total ? `Step ${p.step_done} of ${p.step_total}` : 'Running'
}

/** step_done / step_total; null while the total is unknown. */
export function progressShare(p: BenchmarkRunProgress): number | null {
  return p.step_total ? p.step_done / p.step_total : null
}

/** Rounds held before giving up, out of the rounds configured. */
export function heldOf(denial: BenchmarkArmDetail['denial'] | null | undefined): Held | null {
  if (!denial) return null
  const held = denial.flipped ? Math.max((denial.flip_round ?? 1) - 1, 0) : denial.rounds
  return { held, of: denial.limit || denial.rounds }
}

function dayClock(value: string | null | undefined): string | null {
  const stamp = dayTime(utcStamp(value))
  return stamp === DASH ? null : stamp.replace(', ', ' ')
}

/** The article window of a run: the method's own bounds, else the run's window before it started. */
function articleBounds(report: BenchmarkRunReport): { from: string; to: string } | null {
  const { method, run } = report
  const from = dayClock(method.articles_from)
  const to = dayClock(method.articles_to)
  if (from && to) return { from, to }
  const start = utcStamp(run.created_at)
  if (!start || typeof run.window_days !== 'number' || run.window_days <= 0) return null
  const end = new Date(start)
  if (Number.isNaN(end.getTime())) return null
  const begin = new Date(end.getTime() - run.window_days * 86_400_000)
  return { from: dayClock(begin.toISOString())!, to: dayClock(end.toISOString())! }
}

/** `9 articles published 29 Sep 2026 06:00 to 30 Sep 2026 06:00`, with only the parts known. */
export function articlesText(report: BenchmarkRunReport): string | null {
  const n = report.run.articles
  const bounds = articleBounds(report)
  const range = bounds ? `published ${bounds.from} to ${bounds.to}` : null
  if (typeof n === 'number') {
    const head = `${count(n)} ${n === 1 ? 'article' : 'articles'}`
    return range ? `${head} ${range}` : head
  }
  return range ? `Articles ${range}` : null
}

/** Questions removed by the web check; null until the check reports them. */
export function webRemoved(report: BenchmarkRunReport): number | null {
  return report.funnel.removed.web_answerable ?? null
}

/** Kinds in the generator registry's order, trick last unless the server places it. */
export function methodKinds(report: BenchmarkRunReport): string[] {
  let kinds = report.method.kinds
  if (!kinds.length) {
    const seen = new Set(report.models.flatMap((m) => m.kinds.map((k) => k.generator)))
    kinds = Object.keys(KIND_LABEL).filter((g) => seen.has(g))
  }
  return kinds.some(isTrick) ? kinds : [...kinds, TRICK_GENERATOR]
}

/** Questions of a kind asked to each model; null when no model reports kinds. */
export function kindAsked(report: BenchmarkRunReport, generator: string): number | null {
  if (isTrick(generator)) return report.method.trick
  if (!report.models.length) return null
  for (const m of report.models) {
    const k = m.kinds.find((x) => x.generator === generator)
    if (k) return k.asked
  }
  return 0
}

/** Repeats per question across all temperatures; null when the block did not run. */
export function repeatsTotal(report: BenchmarkRunReport): number | null {
  const r = report.method.repeats
  if (!r?.trials) return null
  return r.trials * Math.max(r.temperatures.length, 1)
}

/** Status chip of a job that asked no model, in place of Published/Private; null otherwise. */
export function runStateLabel(
  run: Pick<BenchmarkRunSummary, 'build_only' | 'state'>,
): string | null {
  if (!run.build_only) return null
  if (run.state === 'failed') return 'Failed'
  if (run.state === 'cancelled') return 'Cancelled'
  return 'Build only'
}

/** `$1.23`; `<$0.01` for a spend below a cent. */
export function usdText(usd: number): string {
  if (usd > 0 && usd < 0.005) return '<$0.01'
  return `$${usd.toFixed(2)}`
}

/** The job's OpenRouter spend: the balance difference, else the per-call sum. */
export function runCost(method: BenchmarkRunReport['method']): number | null {
  const cost = method.cost
  if (!cost) return null
  if (typeof cost.usd === 'number') return cost.usd
  return cost.usd_calls > 0 ? cost.usd_calls : null
}

/** `GPT-5.1 · judged by Claude Sonnet 5`; null when no web check model is known. */
export function webCheckText(method: BenchmarkRunReport['method']): string | null {
  if (!method.web_check_model) return null
  const model = modelName(method.web_check_model)
  return method.web_check_judge
    ? `${model} · judged by ${modelName(method.web_check_judge)}`
    : model
}

/** "Settings for this run" rows; null values show as a dash, optional rows are left out. */
export function methodSettings(report: BenchmarkRunReport): SettingRow[] {
  const { method, funnel } = report
  const written =
    funnel.written === null
      ? null
      : method.generator_model
        ? `${count(funnel.written)}, by ${modelName(method.generator_model)} inside your Syft Space`
        : count(funnel.written)
  const removed = webRemoved(report)
  const trick = funnel.trick
  const asked = trick
    ? `${count(funnel.asked)}, plus ${trick} trick ${trick === 1 ? 'question' : 'questions'}`
    : count(funnel.asked)
  const judges = method.judges.length ? method.judges : report.judges
  const rounds = method.denial_rounds
  const repeats = repeatsTotal(report)
  const webCheck = webCheckText(method)
  const cost = runCost(method)
  const rows: (SettingRow | null)[] = [
    { key: 'articles', label: 'Articles', value: articlesText(report) },
    { key: 'written', label: 'Questions written', value: written },
    {
      key: 'removed',
      label: 'Removed by the web check',
      value: removed === null ? null : count(removed),
    },
    webCheck ? { key: 'webcheck', label: 'Web check', value: webCheck } : null,
    { key: 'asked', label: 'Questions asked', value: asked },
    {
      key: 'models',
      label: 'Models tested',
      value: report.models.length ? report.models.map((m) => modelName(m.model)).join(', ') : null,
    },
    {
      key: 'judges',
      label: 'Judges',
      value: judges.length ? judges.map(modelName).join(', ') : null,
    },
    {
      key: 'rounds',
      label: 'Challenge rounds',
      value: rounds ? `Up to ${rounds} per right answer` : null,
    },
    {
      key: 'repeats',
      label: 'Repeats',
      value: repeats
        ? `${repeats} per question${
            report.method.repeats?.temperatures.length === 2
              ? ', at a steady and a looser setting'
              : ''
          }`
        : null,
    },
    cost === null
      ? null
      : {
          key: 'cost',
          label: 'Cost',
          value: usdText(cost),
          tip: 'OpenRouter spend during this run.',
        },
    { key: 'profile', label: 'Method version', value: method.profile },
  ]
  return rows.filter((row): row is SettingRow => row !== null)
}
