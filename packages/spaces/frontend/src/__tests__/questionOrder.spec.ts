import { describe, expect, it } from 'vitest'
import {
  KIND_ORDER,
  compareKinds,
  sortKinds,
  sortQuestions,
} from '@/components/benchmark/questionOrder'
import { methodKinds } from '@/components/benchmark/report/selectors'
import { KINDS } from '@/components/benchmark/kinds'
import { runReport } from './reportFixtures'

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
