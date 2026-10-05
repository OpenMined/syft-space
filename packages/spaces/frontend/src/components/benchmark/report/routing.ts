import type { LocationQuery, RouteLocationRaw } from 'vue-router'

/** The endpoint page tab that hosts benchmark results. */
export const RESULTS_TAB = 'results'

/** Query keys owned by the results tab; dropped when another tab is opened. */
export const RESULTS_QUERY_KEYS = ['job', 'model', 'screen', 'view', 'run'] as const

/** Screens of one run: its summary and method, and three about one model. */
export type RunScreen = 'run' | 'method' | 'model' | 'questions' | 'checks'

export type ResultsView =
  | { kind: 'list' }
  | { kind: 'run'; jobId: string; screen: RunScreen; modelId: string | null }
  | { kind: 'technical' }

const MODEL_SCREENS = new Set<RunScreen>(['model', 'questions', 'checks'])

function single(value: LocationQuery[string] | undefined): string | null {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' && first !== '' ? first : null
}

/** Which results screen the query describes. */
export function readResultsView(query: LocationQuery): ResultsView {
  if (single(query.view) === 'technical') return { kind: 'technical' }
  const jobId = single(query.job)
  if (!jobId) return { kind: 'list' }
  const modelId = single(query.model)
  const asked = single(query.screen)
  if (asked === 'method') return { kind: 'run', jobId, screen: 'method', modelId: null }
  if (!modelId) return { kind: 'run', jobId, screen: 'run', modelId: null }
  const screen = asked && MODEL_SCREENS.has(asked as RunScreen) ? (asked as RunScreen) : 'model'
  return { kind: 'run', jobId, screen, modelId }
}

/** The query with every results-tab key removed. */
export function withoutResultsQuery(query: LocationQuery): LocationQuery {
  const rest = { ...query }
  for (const key of RESULTS_QUERY_KEYS) delete rest[key]
  return rest
}

function at(query: Record<string, string>): RouteLocationRaw {
  return { query: { tab: RESULTS_TAB, ...query } }
}

export function runsListLocation(): RouteLocationRaw {
  return at({})
}

export function runLocation(jobId: string): RouteLocationRaw {
  return at({ job: jobId })
}

export function methodLocation(jobId: string): RouteLocationRaw {
  return at({ job: jobId, screen: 'method' })
}

export function modelLocation(jobId: string, modelId: string): RouteLocationRaw {
  return at({ job: jobId, model: modelId })
}

export function questionsLocation(jobId: string, modelId: string): RouteLocationRaw {
  return at({ job: jobId, model: modelId, screen: 'questions' })
}

export function checksLocation(jobId: string, modelId: string): RouteLocationRaw {
  return at({ job: jobId, model: modelId, screen: 'checks' })
}

export function technicalLocation(cardId?: string | null): RouteLocationRaw {
  return at(cardId ? { view: 'technical', run: cardId } : { view: 'technical' })
}
