import { describe, expect, it } from 'vitest'
import {
  buildText,
  countsText,
  droppedLines,
  droppedTotal,
  readText,
  stoppedLabel,
  hasDetails,
  outcomeLabel,
  reasonText,
  writtenInText,
} from '@/components/benchmark/filter'
import {
  methodSettings,
  runCost,
  runStateLabel,
  usdText,
  webCheckText,
} from '@/components/benchmark/report/selectors'
import type { BenchmarkWebCheck } from '@/api/types'
import { runReport } from './reportFixtures'

function webCheck(over: Partial<BenchmarkWebCheck> = {}): BenchmarkWebCheck {
  return {
    model: 'openai/gpt-5.1',
    judge: 'google/gemini-3.1-pro-preview',
    answer: '',
    verdict: '',
    reasoning: '',
    citations: [],
    searches: null,
    engine: 'plugin',
    searched: null,
    search_unused: false,
    error: null,
    checked_at: null,
    ...over,
  }
}

describe('filter decisions', () => {
  it('labels outcomes and counts', () => {
    expect(outcomeLabel('removed')).toBe('Removed')
    expect(countsText({ kept: 3, removed: 2, failed: 0, skipped: 0 })).toBe('3 kept · 2 removed')
    expect(countsText({})).toBe('')
  })

  it('words the reason from its code and keeps a fuller note', () => {
    expect(reasonText({ reason: 'web_answerable', reason_code: 'web_answerable' })).toBe(
      'Answerable from the web',
    )
    expect(reasonText({ reason: 'web_answerable', reason_code: null })).toBe(
      'Answerable from the web',
    )
    expect(reasonText({ reason: 'date not in text', reason_code: 'grounding' })).toBe(
      'Not supported by the article: date not in text',
    )
    expect(reasonText({ reason: 'timeout', reason_code: 'other' })).toBe('timeout')
    expect(reasonText({ reason: '', reason_code: null })).toBe('')
  })

  it('names the earlier run a question came from', () => {
    expect(
      writtenInText({
        earlier: false,
        written_by_job_at: null,
        written_at: '2026-09-30T10:00:00Z',
      }),
    ).toBeNull()
    expect(
      writtenInText({
        earlier: true,
        written_by_job_at: '2026-09-29T10:00:00Z',
        written_at: '2026-09-30T10:00:00Z',
      }),
    ).toBe('Written in 29 Sep 2026')
    expect(
      writtenInText({ earlier: true, written_by_job_at: null, written_at: '2026-09-30T10:00:00Z' }),
    ).toBe('Written in 30 Sep 2026')
  })

  it('unfolds only a web check with something to show', () => {
    expect(hasDetails(null)).toBe(false)
    expect(hasDetails(webCheck())).toBe(false)
    expect(hasDetails(webCheck({ answer: 'Paris' }))).toBe(true)
    expect(hasDetails(webCheck({ citations: [{ url: 'https://a.b' }] }))).toBe(true)
  })

  it('sums up a build-only job', () => {
    expect(buildText(null)).toBeNull()
    expect(
      buildText({ written: 12, checked: 12, kept: 8, removed: 4, failed: 0, skipped: 0 }),
    ).toBe('12 written · 4 removed')
  })
})

describe('how tested: web check and cost', () => {
  it('prefers the balance difference, falls back to the per-call sum', () => {
    const base = runReport().method
    expect(runCost(base)).toBeNull()
    expect(
      runCost({ ...base, cost: { usd: 1.234, spend_before: 1, spend_after: 2.234, usd_calls: 1 } }),
    ).toBe(1.234)
    expect(
      runCost({ ...base, cost: { usd: null, spend_before: null, spend_after: 2, usd_calls: 0.5 } }),
    ).toBe(0.5)
    expect(
      runCost({
        ...base,
        cost: { usd: null, spend_before: null, spend_after: null, usd_calls: 0 },
      }),
    ).toBeNull()
    expect(usdText(1.234)).toBe('$1.23')
    expect(usdText(0.001)).toBe('<$0.01')
    expect(usdText(0)).toBe('$0.00')
  })

  it('names the web check model and its judge', () => {
    const base = runReport().method
    expect(webCheckText(base)).toBeNull()
    expect(webCheckText({ ...base, web_check_model: 'openai/gpt-5.1' })).toBe('GPT-5.1')
    expect(
      webCheckText({
        ...base,
        web_check_model: 'openai/gpt-5.1',
        web_check_judge: 'google/gemini-3.1-pro-preview',
      }),
    ).toBe('GPT-5.1 · judged by Gemini 3.1 Pro')
  })

  it('hides the rows when their value is missing', () => {
    const keys = (r: ReturnType<typeof runReport>) => methodSettings(r).map((row) => row.key)
    expect(keys(runReport())).not.toContain('webcheck')
    expect(keys(runReport())).not.toContain('cost')
    const base = runReport()
    const rows = methodSettings(
      runReport({
        method: {
          ...base.method,
          web_check_model: 'openai/gpt-5.1',
          cost: { usd: 0.42, spend_before: 1, spend_after: 1.42, usd_calls: 0.4 },
        },
      }),
    )
    expect(rows.find((r) => r.key === 'webcheck')?.value).toBe('GPT-5.1')
    const cost = rows.find((r) => r.key === 'cost')
    expect(cost?.value).toBe('$0.42')
    expect(cost?.tip).toBe('OpenRouter spend during this run.')
  })
})

describe('runs list state chip', () => {
  it('marks build-only jobs only', () => {
    expect(runStateLabel({ build_only: false, state: 'failed' })).toBeNull()
    expect(runStateLabel({ build_only: true, state: 'succeeded' })).toBe('Build only')
    expect(runStateLabel({ build_only: true, state: 'cancelled' })).toBe('Cancelled')
  })
})

describe('generation per kind', () => {
  const kind = {
    unit: 'passage' as const,
    units_read: 12,
    units_available: 40,
    failed_units: 0,
    dropped: { duplicate: 1, 'no mask': 3, 'over budget': 0 },
  }

  it('words the stop reason as a chip', () => {
    expect(stoppedLabel('budget reached')).toBe('Budget reached')
    expect(stoppedLabel('ran out of material')).toBe('Out of material')
    expect(stoppedLabel('failure streak')).toBe('Failures')
    expect(stoppedLabel('cancelled')).toBe('Cancelled')
  })

  it('sums drops and lists reasons largest first', () => {
    expect(droppedTotal(kind)).toBe(4)
    expect(droppedLines(kind)).toEqual(['no mask: 3', 'duplicate: 1'])
  })

  it('shows what was read of what was available', () => {
    expect(readText(kind)).toBe('12 / 40 passages')
    expect(readText({ ...kind, unit: 'article', failed_units: 2 })).toBe(
      '12 / 40 articles, 2 failed',
    )
  })
})
