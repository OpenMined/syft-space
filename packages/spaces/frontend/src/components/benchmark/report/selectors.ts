/** Pure helpers that turn the server's report shapes into words. */
import type { BenchmarkArmDetail, BenchmarkRunProgress, BenchmarkRunReport } from '@/api/types'
import { runningDetail } from '@/composables/useBenchmarkJobs'
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

/** Phase and step of an in-progress run, in words. */
export function progressText(p: BenchmarkRunProgress): string {
  if (p.state === 'queued') return 'Queued'
  const detail = runningDetail({ ...p, id: p.job_id, arm: '', error: '', finished_at: null })
  return detail || 'Running'
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

/** "How this was tested" rows, from the run's own method record. */
export function methodSettings(report: BenchmarkRunReport): SettingRow[] {
  const { method, run, funnel } = report
  const articles = run.articles

  const from = shortStamp(method.articles_from)
  const to = shortStamp(method.articles_to)
  let articlesText: string | null = null
  if (typeof articles === 'number') {
    const noun = articles === 1 ? 'article' : 'articles'
    articlesText =
      from && to ? `${articles} ${noun} published ${from} to ${to}` : `${articles} ${noun}`
  }

  const kinds = method.kinds.filter((g) => !isTrick(g)).length
  const trick = method.trick
  const allKinds = Object.keys(KIND_LABEL).filter((g) => !isTrick(g)).length
  let kindsText: string | null = null
  if (kinds) {
    kindsText =
      kinds >= allKinds
        ? `${kinds} kinds, from filling in a name to explaining a story simply`
        : `${kinds} ${kinds === 1 ? 'kind' : 'kinds'}`
    if (trick)
      kindsText += `, plus ${trick} trick ${trick === 1 ? 'question' : 'questions'} with no answer`
  }

  const passages = method.context_docs
  const asked =
    funnel.asked || funnel.trick
      ? `Twice per question: once with web search only, once also given ${
          passages ? `up to ${passages} ${passages === 1 ? 'passage' : 'passages'}` : 'passages'
        } from your archive`
      : null

  const judges = method.judges.length ? method.judges : report.judges
  const next = shortStamp(method.next_run_at)

  return [
    { key: 'articles', label: 'Articles', value: articlesText },
    {
      key: 'writtenBy',
      label: 'Questions written by',
      value: method.generator_model
        ? `${modelName(method.generator_model)}, running inside your Syft Space`
        : null,
    },
    { key: 'kinds', label: 'Kinds of question', value: kindsText },
    { key: 'asked', label: 'How models were asked', value: asked },
    {
      key: 'judges',
      label: 'Judges',
      value: judges.length
        ? `${judges.map(modelName).join(', ')}. A judge never grades a model from its own company.`
        : null,
    },
    {
      key: 'leaves',
      label: 'What leaves your organization',
      value:
        'Short passages go to the models being tested, only to answer these questions. Scores are shared only if you publish.',
    },
    {
      key: 'profile',
      label: 'Method version',
      value: method.profile
        ? `${method.profile}, recorded with every run so results stay comparable`
        : null,
    },
    {
      key: 'next',
      label: 'Next run',
      value: next ? `${next}, on the following 24 hours of articles` : null,
    },
  ]
}
