import { describe, expect, it } from 'vitest'
import { daySpan } from '@/components/benchmark/report/figures'
import {
  articlesText,
  otherNotAsked,
  runHeaderText,
  runStateLabel,
  stoppedLabel,
} from '@/components/benchmark/report/selectors'
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

  it('shows the count only when the articles have no dates', () => {
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

describe('the funnel', () => {
  it('counts every question of the run that was not asked, with the reasons', () => {
    const report = runReport({
      funnel: {
        written: 120,
        removed: { web_answerable: 100, rotation: 4, grounding: 1 },
        unchecked: 1,
        asked: 14,
        trick: 2,
      },
    })
    const other = otherNotAsked(report)
    expect(other?.total).toBe(6)
    expect(other?.tip).toBe(
      'Rotated out: 4 · Not supported by the article: 1 · Web check not finished: 1',
    )
    // written = web check + other reasons + asked
    expect(100 + other!.total + report.funnel.asked).toBe(report.funnel.written)
  })

  it('has nothing to add when only the web check removed questions', () => {
    const report = runReport({
      funnel: {
        written: 70,
        removed: { web_answerable: 57 },
        asked: 13,
        trick: 1,
      },
    })
    expect(otherNotAsked(report)).toBeNull()
  })
})
