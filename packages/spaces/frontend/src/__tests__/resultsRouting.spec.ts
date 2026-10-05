import { describe, expect, it } from 'vitest'
import {
  readResultsView,
  runReportLocation,
  runsListLocation,
  technicalLocation,
  withoutResultsQuery,
} from '@/components/benchmark/report/routing'

describe('results routing helpers', () => {
  it('builds the runs list location with only the tab', () => {
    expect(runsListLocation()).toEqual({ query: { tab: 'results' } })
  })

  it('builds the report location with an optional model', () => {
    expect(runReportLocation('j1')).toEqual({ query: { tab: 'results', job: 'j1' } })
    expect(runReportLocation('j1', null)).toEqual({ query: { tab: 'results', job: 'j1' } })
    expect(runReportLocation('j1', 'm1')).toEqual({
      query: { tab: 'results', job: 'j1', model: 'm1' },
    })
  })

  it('builds the technical location with an optional card', () => {
    expect(technicalLocation()).toEqual({ query: { tab: 'results', view: 'technical' } })
    expect(technicalLocation('c1')).toEqual({
      query: { tab: 'results', view: 'technical', run: 'c1' },
    })
  })

  it('reads the view from the query', () => {
    expect(readResultsView({ tab: 'results' })).toEqual({ kind: 'list' })
    expect(readResultsView({ job: '' })).toEqual({ kind: 'list' })
    expect(readResultsView({ job: 'j1' })).toEqual({ kind: 'report', jobId: 'j1', modelId: null })
    expect(readResultsView({ job: ['j1', 'j2'], model: 'm1' })).toEqual({
      kind: 'report',
      jobId: 'j1',
      modelId: 'm1',
    })
    expect(readResultsView({ view: 'technical', job: 'j1', model: 'm1' })).toEqual({
      kind: 'technical',
    })
  })

  it('drops results-only keys', () => {
    expect(
      withoutResultsQuery({
        tab: 'results',
        job: 'j',
        model: 'm',
        view: 'technical',
        run: 'r',
        x: '1',
      }),
    ).toEqual({ tab: 'results', x: '1' })
  })
})
