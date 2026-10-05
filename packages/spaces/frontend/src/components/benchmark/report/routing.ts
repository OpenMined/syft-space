import type { LocationQuery, RouteLocationRaw } from 'vue-router'

/** The endpoint page tab that hosts benchmark results. */
export const RESULTS_TAB = 'results'

/** Query keys owned by the results tab; dropped when another tab is opened. */
export const RESULTS_QUERY_KEYS = ['job', 'model', 'view', 'run'] as const

export type ResultsView =
  | { kind: 'list' }
  | { kind: 'report'; jobId: string; modelId: string | null }
  | { kind: 'technical' }

function single(value: LocationQuery[string] | undefined): string | null {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' && first !== '' ? first : null
}

/** Which results screen the query describes. */
export function readResultsView(query: LocationQuery): ResultsView {
  if (single(query.view) === 'technical') return { kind: 'technical' }
  const jobId = single(query.job)
  if (jobId) return { kind: 'report', jobId, modelId: single(query.model) }
  return { kind: 'list' }
}

/** The query with every results-tab key removed. */
export function withoutResultsQuery(query: LocationQuery): LocationQuery {
  const rest = { ...query }
  for (const key of RESULTS_QUERY_KEYS) delete rest[key]
  return rest
}

export function runsListLocation(): RouteLocationRaw {
  return { query: { tab: RESULTS_TAB } }
}

export function runReportLocation(jobId: string, modelId?: string | null): RouteLocationRaw {
  const query: Record<string, string> = { tab: RESULTS_TAB, job: jobId }
  if (modelId) query.model = modelId
  return { query }
}

export function technicalLocation(cardId?: string | null): RouteLocationRaw {
  const query: Record<string, string> = { tab: RESULTS_TAB, view: 'technical' }
  if (cardId) query.run = cardId
  return { query }
}
