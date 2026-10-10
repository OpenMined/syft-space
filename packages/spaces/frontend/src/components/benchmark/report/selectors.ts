/** Pure helpers that turn the server's report shapes into words. */
import type {
  BenchmarkArmDetail,
  BenchmarkRunProgress,
  BenchmarkRunReport,
  BenchmarkRunSummary,
} from '@/api/types'
import { count, DASH, daySpan } from './figures'
import { customerCost, runDuration, tookText } from './timeCost'
import { KIND_LABEL, modelName, type Behavior } from './labels'
import { sortKinds } from '../questionOrder'
import { TRICK_GENERATOR, type Held, type SettingRow } from './types'

export function isOutcome(verdict: string | null | undefined): boolean {
  return (
    verdict === 'correct' ||
    verdict === 'abstain' ||
    verdict === 'hallucinate' ||
    verdict === 'web_sourced'
  )
}

export function isTrick(generator: string | null | undefined): boolean {
  return generator === TRICK_GENERATOR
}

export { shortStamp, utcStamp } from './figures'

/** `Step 11 of 15` for an in-progress run. */
export function progressText(p: BenchmarkRunProgress): string {
  if (p.state === 'queued') return 'Queued'
  return p.step_total ? `Step ${p.step_done} of ${p.step_total}` : 'Running'
}

/** step_done / step_total; null while the total is unknown. */
export function progressShare(p: BenchmarkRunProgress): number | null {
  return p.step_total ? p.step_done / p.step_total : null
}

/** One square per trick question, made-up answers first, then answers from the web. */
export function trickSquares(asked: number, madeUp: number, web: number): Behavior[] {
  return Array.from({ length: asked }, (_, i) =>
    i < madeUp ? 'made_up' : i < madeUp + web ? 'web_sourced' : 'declined',
  )
}

/** The trick check in one or two sentences. */
export function trickReading(asked: number, madeUp: number, web: number): string {
  if (!asked) return DASH
  if (!madeUp && !web) return `Refused all ${asked}. It hallucinated an answer to none of them.`
  const made = `Hallucinated an answer to ${madeUp} of ${asked}.`
  return web ? `${made} Answered ${web} from the web.` : made
}

/** Rounds held before giving up, out of the rounds configured. */
export function heldOf(denial: BenchmarkArmDetail['denial'] | null | undefined): Held | null {
  if (!denial) return null
  const held = denial.flipped ? Math.max((denial.flip_round ?? 1) - 1, 0) : denial.rounds
  return { held, of: denial.limit || denial.rounds }
}

type ArticleFacts = Pick<
  BenchmarkRunSummary,
  'articles' | 'articles_first' | 'articles_last' | 'articles_dated' | 'articles_new'
>

function plural(n: number, word: string): string {
  return `${count(n)} ${n === 1 ? word : `${word}s`}`
}

/** `10 articles published 5–9 Oct · 4 new this run`, from the asked questions' own article dates. */
export function articlesText(
  run: ArticleFacts,
  thisYear: number = new Date().getFullYear(),
): string | null {
  const n = run.articles
  const fresh = typeof run.articles_new === 'number' ? run.articles_new : null
  if (typeof n !== 'number') return fresh === null ? null : plural(fresh, 'new article')
  const span =
    run.articles_first && run.articles_last
      ? daySpan(run.articles_first, run.articles_last, thisYear)
      : null
  const dated = run.articles_dated
  let text = plural(n, 'article')
  if (span) {
    const some = typeof dated === 'number' && dated > 0 && dated < n
    text += some ? `, ${count(dated)} published ${span}` : ` published ${span}`
  }
  return fresh === null ? text : `${text} · ${count(fresh)} new this run`
}

/** Whether any answer in the run was graded as backed by its web search. */
export function hasWebSourced(report: BenchmarkRunReport): boolean {
  return report.models.some(
    (m) =>
      (m.tally.alone.web_sourced ?? 0) > 0 ||
      (m.tally.with.web_sourced ?? 0) > 0 ||
      (m.checks.trick_web ?? 0) > 0 ||
      (m.checks.trick_alone_web ?? 0) > 0,
  )
}

/** Questions removed by the web check; null until the check reports them. */
export function webRemoved(report: BenchmarkRunReport): number | null {
  return report.funnel.removed.web_answerable ?? null
}

/** The run's kinds, trick questions included, in the canonical order. */
export function methodKinds(report: BenchmarkRunReport): string[] {
  let kinds = report.method.kinds
  if (!kinds.length) {
    const seen = new Set(report.models.flatMap((m) => m.kinds.map((k) => k.generator)))
    kinds = Object.keys(KIND_LABEL).filter((g) => seen.has(g))
  }
  return sortKinds(kinds.some(isTrick) ? kinds : [...kinds, TRICK_GENERATOR])
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
  run: Pick<BenchmarkRunSummary, 'build_only' | 'state' | 'stopped'>,
): string | null {
  if (!run.build_only) return null
  if (run.state === 'failed') return 'Failed'
  if (run.state === 'cancelled') return stoppedLabel(run) ?? 'Cancelled'
  return 'Build only'
}

const STOPPED = {
  owner: { label: 'Stopped', tip: 'You stopped this run before it finished.' },
  spending_cap: {
    label: 'Stopped: spending cap',
    tip: 'Stopped when its spend reached the cap for one run.',
  },
} as const

/** Chip of a run stopped before it finished; null otherwise. */
export function stoppedLabel(run: Pick<BenchmarkRunSummary, 'stopped'>): string | null {
  return run.stopped ? STOPPED[run.stopped].label : null
}

export function stoppedTip(run: Pick<BenchmarkRunSummary, 'stopped'>): string | undefined {
  return run.stopped ? STOPPED[run.stopped].tip : undefined
}

/** `$1.23`; `<$0.01` for a spend below a cent. */
export function usdText(usd: number): string {
  if (usd > 0 && usd < 0.005) return '<$0.01'
  return `$${usd.toFixed(2)}`
}

/** `23 questions from 10 articles published 5–9 Oct · 4 new this run · took 54 min · cost $18.40`. */
export function runHeaderText(
  report: BenchmarkRunReport,
  thisYear: number = new Date().getFullYear(),
): string | null {
  const seconds = runDuration(report.run)
  const cost = customerCost(report.method)
  const asked = report.run.questions
  const articles = articlesText(report.run, thisYear)
  const questions = typeof asked === 'number' ? plural(asked, 'question') : null
  const joined = questions && articles && typeof report.run.articles === 'number'
  const parts = [
    ...(joined ? [`${questions} from ${articles}`] : [questions, articles]),
    seconds === null ? null : `took ${tookText(seconds)}`,
    cost === null ? null : `cost ${usdText(cost)}`,
  ].filter((p): p is string => !!p)
  if (!parts.length) return null
  const text = parts.join(' · ')
  return text.charAt(0).toUpperCase() + text.slice(1)
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
  const cost = customerCost(method)
  const seconds = runDuration(report.run)
  const rows: (SettingRow | null)[] = [
    { key: 'articles', label: 'Articles', value: articlesText(report.run) },
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
          tip: 'All model calls in this run.',
        },
    seconds === null ? null : { key: 'duration', label: 'Duration', value: tookText(seconds) },
    { key: 'profile', label: 'Method version', value: method.profile },
  ]
  return rows.filter((row): row is SettingRow => row !== null)
}
