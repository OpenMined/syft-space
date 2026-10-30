import { describe, expect, it } from 'vitest'
import {
  behaviorOf,
  outcomeLabel,
  verdictLabel,
  verdictTip,
  verdictTone,
} from '@/components/benchmark/report/labels'
import {
  hasIncomplete,
  hasWebSourced,
  trickReading,
  trickSquares,
} from '@/components/benchmark/report/selectors'
import { modelReport, OPUS, runReport } from './reportFixtures'

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

  it('labels incomplete and tells whether a run has any', () => {
    expect(verdictLabel('incomplete')).toBe('Incomplete')
    expect(verdictTip('incomplete')).toBe('Left out key facts but stated nothing false.')
    expect(outcomeLabel('tiered_explanation', 'incomplete')).toBe('Incomplete')
    expect(hasIncomplete(runReport({ models: [modelReport(OPUS)] }))).toBe(false)
    const m = modelReport(OPUS)
    const partial = { ...m, tally: { ...m.tally, with: { ...m.tally.with, incomplete: 1 } } }
    expect(hasIncomplete(runReport({ models: [partial] }))).toBe(true)
  })
})
