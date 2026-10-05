import { describe, expect, it } from 'vitest'
import {
  checksLocation,
  methodLocation,
  modelLocation,
  questionsLocation,
  readResultsView,
  runLocation,
  runsListLocation,
  technicalLocation,
  withoutResultsQuery,
} from '@/components/benchmark/report/routing'

describe('results routing', () => {
  it('builds a location for every screen', () => {
    expect(runsListLocation()).toEqual({ query: { tab: 'results' } })
    expect(runLocation('j1')).toEqual({ query: { tab: 'results', job: 'j1' } })
    expect(methodLocation('j1')).toEqual({ query: { tab: 'results', job: 'j1', screen: 'method' } })
    expect(modelLocation('j1', 'm1')).toEqual({ query: { tab: 'results', job: 'j1', model: 'm1' } })
    expect(questionsLocation('j1', 'm1')).toEqual({
      query: { tab: 'results', job: 'j1', model: 'm1', screen: 'questions' },
    })
    expect(checksLocation('j1', 'm1')).toEqual({
      query: { tab: 'results', job: 'j1', model: 'm1', screen: 'checks' },
    })
    expect(technicalLocation()).toEqual({ query: { tab: 'results', view: 'technical' } })
    expect(technicalLocation('c1')).toEqual({
      query: { tab: 'results', view: 'technical', run: 'c1' },
    })
  })

  it('reads every screen back from the query', () => {
    expect(readResultsView({ tab: 'results' })).toEqual({ kind: 'list' })
    expect(readResultsView({ job: '' })).toEqual({ kind: 'list' })
    expect(readResultsView({ job: 'j1' })).toEqual({
      kind: 'run',
      jobId: 'j1',
      screen: 'run',
      modelId: null,
    })
    expect(readResultsView({ job: 'j1', screen: 'method', model: 'm1' })).toEqual({
      kind: 'run',
      jobId: 'j1',
      screen: 'method',
      modelId: null,
    })
    expect(readResultsView({ job: ['j1', 'j2'], model: 'm1' })).toEqual({
      kind: 'run',
      jobId: 'j1',
      screen: 'model',
      modelId: 'm1',
    })
    expect(readResultsView({ job: 'j1', model: 'm1', screen: 'questions' })).toMatchObject({
      screen: 'questions',
    })
    expect(readResultsView({ job: 'j1', model: 'm1', screen: 'checks' })).toMatchObject({
      screen: 'checks',
    })
    expect(readResultsView({ job: 'j1', model: 'm1', screen: 'bogus' })).toMatchObject({
      screen: 'model',
    })
    // A model screen without a model falls back to the run summary.
    expect(readResultsView({ job: 'j1', screen: 'questions' })).toMatchObject({ screen: 'run' })
    expect(readResultsView({ view: 'technical', job: 'j1', model: 'm1' })).toEqual({
      kind: 'technical',
    })
  })

  it('drops every results key', () => {
    expect(
      withoutResultsQuery({
        tab: 'x',
        job: 'j',
        model: 'm',
        screen: 's',
        view: 'v',
        run: 'r',
        keep: '1',
      }),
    ).toEqual({ tab: 'x', keep: '1' })
  })
})
