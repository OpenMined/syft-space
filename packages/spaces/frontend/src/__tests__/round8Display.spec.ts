import { describe, expect, it } from 'vitest'
import { daySpan } from '@/components/benchmark/report/figures'
import {
  articlesText,
  runHeaderText,
  runStateLabel,
  stoppedLabel,
} from '@/components/benchmark/report/selectors'
import { maskedBy, maskedCounts } from '@/components/benchmark/filter'
import { runReport, runSummary } from './reportFixtures'

describe('article day span', () => {
  it('names the month once inside a month', () => {
    expect(daySpan('2026-10-05', '2026-10-09', 2026)).toBe('5–9 Oct')
    expect(daySpan('2026-10-09', '2026-10-09', 2026)).toBe('9 Oct')
  })

  it('spans months and years', () => {
    expect(daySpan('2026-09-28', '2026-10-03', 2026)).toBe('28 Sep–3 Oct')
    expect(daySpan('2025-12-28', '2026-01-03', 2026)).toBe('28 Dec 2025–3 Jan 2026')
    expect(daySpan('2025-10-05', '2025-10-09', 2026)).toBe('5–9 Oct 2025')
  })

  it('gives up on a bad date', () => {
    expect(daySpan('soon', '2026-10-09', 2026)).toBeNull()
  })
})

describe('run articles', () => {
  const run = {
    articles: 10,
    articles_first: '2026-10-05',
    articles_last: '2026-10-09',
    articles_dated: 10,
    articles_new: 4,
  }

  it('gives the real dates and the new articles', () => {
    expect(articlesText(run, 2026)).toBe('10 articles published 5–9 Oct · 4 new this run')
  })

  it('says how many the dates cover when some have none', () => {
    expect(articlesText({ ...run, articles_dated: 8 }, 2026)).toBe(
      '10 articles, 8 published 5–9 Oct · 4 new this run',
    )
  })

  it('shows the count only for an older run', () => {
    expect(articlesText({ articles: 9 }, 2026)).toBe('9 articles')
    expect(articlesText({ articles: null, articles_new: 4 }, 2026)).toBe('4 new articles')
    expect(articlesText({ articles: null }, 2026)).toBeNull()
  })

  it('leads the header with the questions asked', () => {
    const text = runHeaderText(
      runReport({ run: runSummary('j1', { questions: 23, ...run }) }),
      2026,
    )
    expect(text).toBe('23 questions from 10 articles published 5–9 Oct · 4 new this run')
  })

  it('ignores the configured window', () => {
    const report = runReport({ run: runSummary('j1', { questions: 23, articles: 10 }) })
    report.method.articles_from = '2026-10-08T16:38:00Z'
    report.method.articles_to = '2026-10-09T16:38:00Z'
    expect(runHeaderText(report, 2026)).toBe('23 questions from 10 articles')
  })
})

describe('extractive path', () => {
  it('counts spaCy and LLM questions per masking kind', () => {
    expect(
      maskedCounts({
        spacy: 12,
        llm: 3,
        llm_why: { 'language not recognised': 1, "no spaCy model for 'de'": 2 },
      }),
    ).toEqual({ text: '12 / 3', tip: "no spaCy model for 'de': 2\nlanguage not recognised: 1" })
    expect(maskedCounts({ spacy: null, llm: null, llm_why: null })).toBeNull()
    expect(maskedCounts({})).toBeNull()
  })

  it('names the path of one question', () => {
    expect(maskedBy({ mode: 'spacy', spacy_model: 'en_core_web_sm' })).toEqual({
      label: 'spaCy',
      tip: 'Cut by spaCy (en_core_web_sm).',
    })
    expect(maskedBy({ mode: 'llm', llm_why: 'spaCy not installed' })).toEqual({
      label: 'LLM',
      tip: 'Written by the LLM: spaCy not installed.',
    })
    expect(maskedBy({ options: [] })).toBeNull()
    expect(maskedBy(null)).toBeNull()
  })
})

describe('stopped runs', () => {
  it('says who stopped a run', () => {
    expect(stoppedLabel({ stopped: 'spending_cap' })).toBe('Stopped: spending cap')
    expect(stoppedLabel({ stopped: 'owner' })).toBe('Stopped')
    expect(stoppedLabel({ stopped: null })).toBeNull()
    expect(stoppedLabel({})).toBeNull()
  })

  it('names the cap on a build-only run too', () => {
    const run = { build_only: true, state: 'cancelled', stopped: 'spending_cap' } as const
    expect(runStateLabel(run)).toBe('Stopped: spending cap')
    expect(runStateLabel({ build_only: true, state: 'cancelled' })).toBe('Cancelled')
  })
})
