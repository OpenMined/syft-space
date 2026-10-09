import { describe, expect, it } from 'vitest'
import type { BenchmarkProgressPlan, BenchmarkTextMetricsRow } from '@/api/types'
import {
  behaviorOf,
  outcomeLabel,
  verdictLabel,
  verdictTip,
  verdictTone,
} from '@/components/benchmark/report/labels'
import {
  hasWebSourced,
  methodKinds,
  trickReading,
  trickSquares,
} from '@/components/benchmark/report/selectors'
import {
  KIND_ORDER,
  compareKinds,
  sortKinds,
  sortQuestions,
} from '@/components/benchmark/questionOrder'
import { KINDS } from '@/components/benchmark/setup/setupForm'
import { leftText, msLeft, paceStart, planText } from '@/components/benchmark/setup/progress'
import {
  metricCell,
  metricColumns,
  metricParts,
  metricsLine,
} from '@/components/benchmark/textMetrics'
import { modelReport, OPUS, runReport } from './reportFixtures'

const MIN = 60_000

function plan(over: Partial<BenchmarkProgressPlan> = {}): BenchmarkProgressPlan {
  return {
    questions: 30,
    models: ['openai/gpt-5.1', 'x-ai/grok-4.7'],
    conditions: ['closed_book', 'model_with_context'],
    checks: ['direct', 'denial_loop', 'monte_carlo'],
    skipped_monte_carlo: [],
    passes: 12,
    steps: 360,
    started_at: '2026-10-08T10:00:00',
    ...over,
  }
}

describe('progress plan tooltip', () => {
  it('spells out the plan', () => {
    expect(planText(plan())).toBe('30 questions × 2 models × 2 conditions × 3 checks')
  })

  it('uses singulars and names the Monte Carlo skips', () => {
    const text = planText(
      plan({
        questions: 1,
        models: ['openai/gpt-5.1'],
        conditions: ['closed_book'],
        checks: ['direct'],
        skipped_monte_carlo: ['openai/gpt-5.1'],
      }),
      (id) => id.toUpperCase(),
    )
    expect(text).toBe(
      '1 question × 1 model × 1 condition × 1 check. Monte Carlo skipped: OPENAI/GPT-5.1',
    )
  })

  it('is empty without a plan', () => {
    expect(planText(null)).toBe('')
    expect(planText(undefined)).toBe('')
  })
})

describe('time left', () => {
  const start = paceStart(plan())!

  it('reads the start of the evaluate phase as UTC', () => {
    expect(start).toEqual({ at: Date.parse('2026-10-08T10:00:00Z'), done: 0 })
    expect(paceStart(plan({ started_at: 'nonsense' }))).toBeNull()
    expect(paceStart(null)).toBeNull()
  })

  it('estimates from the pace so far', () => {
    // 90 of 360 in 10 minutes -> 270 left at 9 per minute.
    expect(msLeft(90, 360, start, start.at + 10 * MIN)).toBe(30 * MIN)
  })

  it('waits for 5% of the steps and a minute', () => {
    expect(msLeft(17, 360, start, start.at + 10 * MIN)).toBeNull()
    expect(msLeft(18, 360, start, start.at + 10 * MIN)).not.toBeNull()
    expect(msLeft(100, 360, start, start.at + 59_000)).toBeNull()
    expect(msLeft(0, 360, start, start.at + 10 * MIN)).toBeNull()
  })

  it('has nothing to say without a start, a total, or work left', () => {
    expect(msLeft(90, 360, null, start.at + 10 * MIN)).toBeNull()
    expect(msLeft(0, 0, start, start.at + 10 * MIN)).toBeNull()
    expect(msLeft(360, 360, start, start.at + 10 * MIN)).toBeNull()
  })

  it('words the estimate', () => {
    expect(leftText(null)).toBe('')
    expect(leftText(10_000)).toBe('About 1 min left')
    expect(leftText(24.2 * MIN)).toBe('About 25 min left')
    expect(leftText(60 * MIN)).toBe('About 1 h left')
    expect(leftText(71 * MIN)).toBe('About 1 h 10 min left')
  })
})

describe('text metrics', () => {
  it('lists the scores present in a fixed order', () => {
    const scores = { bertscore_f1: 0.8912, bleu: 0.3104, rougeL_f: 0.48 }
    expect(metricParts(scores).map((p) => p.label)).toEqual(['BLEU', 'ROUGE-L', 'BERTScore'])
    expect(metricsLine(scores)).toBe('BLEU 0.31 · ROUGE-L 0.48 · BERTScore 0.89')
  })

  it('is empty when the answer has none', () => {
    expect(metricsLine(null)).toBe('')
    expect(metricsLine(undefined)).toBe('')
    expect(metricsLine({})).toBe('')
  })

  it('builds the summary columns from every row', () => {
    const rows: BenchmarkTextMetricsRow[] = [
      { model: OPUS, arm: 'alone', counted: 10, scores: { rouge1_f: 0.4 } },
      { model: OPUS, arm: 'with', counted: 9, scores: { bleu: 0.5, rouge1_f: 0.6 } },
    ]
    expect(metricColumns(rows)).toEqual(['bleu', 'rouge1_f'])
    expect(metricCell(rows[0]!, 'bleu')).toBe('—')
    expect(metricCell(rows[1]!, 'bleu')).toBe('0.50')
    expect(metricColumns([])).toEqual([])
  })
})

describe('control outcomes', () => {
  it('labels the web-sourced verdict', () => {
    expect(verdictLabel('web_sourced')).toBe('From the web')
    expect(verdictTip('web_sourced')).toBe('Stated facts its web search supports.')
    expect(verdictTip('correct')).toBe('')
    expect(verdictTone('web_sourced')).toContain('border-transparent')
  })

  it('derives the fine outcome on control questions only', () => {
    expect(behaviorOf('unanswerable_property', 'abstain')).toBe('declined')
    expect(behaviorOf('false_premise', 'correct')).toBe('corrected')
    expect(behaviorOf('false_premise', 'web_sourced')).toBe('web_sourced')
    expect(behaviorOf('unanswerable_property', 'hallucinate')).toBe('made_up')
    expect(behaviorOf('unanswerable_property', 'pending')).toBeNull()
    expect(behaviorOf('qa', 'abstain')).toBeNull()
    expect(outcomeLabel('false_premise', 'hallucinate')).toBe('Hallucinated')
    expect(outcomeLabel('qa', 'hallucinate')).toBe('Hallucinated')
  })

  it('prefers the behaviour the API gives, deriving only as a fallback', () => {
    expect(behaviorOf('unanswerable_property', 'abstain', 'corrected')).toBe('corrected')
    expect(behaviorOf('unanswerable_property', 'abstain', null)).toBe('declined')
    expect(behaviorOf('unanswerable_property', 'abstain', 'nonsense')).toBe('declined')
    expect(behaviorOf('qa', 'abstain', 'declined')).toBeNull()
    expect(outcomeLabel('unanswerable_property', 'abstain', 'corrected')).toBe('Corrected')
  })

  it('orders the trick squares and words the reading', () => {
    expect(trickSquares(4, 1, 1)).toEqual(['made_up', 'web_sourced', 'declined', 'declined'])
    expect(trickReading(0, 0, 0)).toBe('—')
    expect(trickReading(3, 0, 0)).toBe('Refused all 3. It hallucinated an answer to none of them.')
    expect(trickReading(3, 0, 1)).toBe('Hallucinated an answer to 0 of 3. Answered 1 from the web.')
    expect(trickReading(3, 2, 0)).toBe('Hallucinated an answer to 2 of 3.')
  })

  it('tells whether a run has any web-sourced answer', () => {
    expect(hasWebSourced(runReport({ models: [modelReport(OPUS)] }))).toBe(false)
    const m = modelReport(OPUS)
    const withWeb = { ...m, tally: { ...m.tally, alone: { ...m.tally.alone, web_sourced: 1 } } }
    expect(hasWebSourced(runReport({ models: [withWeb] }))).toBe(true)
  })
})

describe('question order', () => {
  it('follows the setup page’s kinds, unknown kinds last alphabetically', () => {
    expect(KIND_ORDER).toEqual(KINDS.map((k) => k.key))
    expect(
      sortKinds(['zeta', 'false_premise', 'qa', 'alpha', 'named_entity_masking', 'qa']),
    ).toEqual(['named_entity_masking', 'qa', 'false_premise', 'alpha', 'zeta'])
    expect(compareKinds('numeric_masking', 'temporal_masking')).toBeLessThan(0)
  })

  it('orders by kind, then creation time, then id', () => {
    const rows = [
      { id: 'b', generator: 'qa', created_at: '2026-10-08T10:00:00' },
      { id: 'x', generator: 'false_premise', created_at: '2026-10-01T10:00:00' },
      { id: 'a', generator: 'qa', created_at: '2026-10-08T10:00:00' },
      { id: 'c', generator: 'qa', created_at: '2026-10-07T10:00:00' },
      { id: 'n', generator: 'named_entity_masking', created_at: '2026-10-09T10:00:00' },
    ]
    const sorted = sortQuestions(rows, (r) => ({
      generator: r.generator,
      createdAt: r.created_at,
      id: r.id,
    }))
    expect(sorted.map((r) => r.id)).toEqual(['n', 'c', 'a', 'b', 'x'])
    expect(rows[0]!.id).toBe('b')
  })

  it('keeps the incoming order within a kind when there is nothing else to go by', () => {
    const rows = [
      { n: 1, generator: 'qa' },
      { n: 2, generator: 'mcq' },
      { n: 3, generator: 'qa' },
      { n: 4, generator: 'mcq' },
    ]
    expect(sortQuestions(rows, (r) => ({ generator: r.generator })).map((r) => r.n)).toEqual([
      2, 4, 1, 3,
    ])
  })

  it('lists a run’s kinds in that order', () => {
    const base = runReport()
    const report = runReport({ method: { ...base.method, kinds: ['qa', 'false_premise', 'mcq'] } })
    expect(methodKinds(report)).toEqual(['mcq', 'qa', 'unanswerable_property', 'false_premise'])
  })
})
