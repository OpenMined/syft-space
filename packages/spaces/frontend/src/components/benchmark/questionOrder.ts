/**
 * The one question order every list follows, same as the benchmark's: kind in the
 * setup page's order (unknown kinds last, alphabetically), then pair creation time,
 * then pair id.
 */
import { KINDS } from './setup/setupForm'

export const KIND_ORDER: readonly string[] = KINDS.map((kind) => kind.key)

/** Position of a kind; unknown kinds share the last place. */
export function kindRank(generator: string): number {
  const at = KIND_ORDER.indexOf(generator)
  return at === -1 ? KIND_ORDER.length : at
}

export function compareKinds(a: string, b: string): number {
  return kindRank(a) - kindRank(b) || (kindRank(a) === KIND_ORDER.length ? cmp(a, b) : 0)
}

/** What a question is ordered by; fields a list does not have are skipped. */
export interface QuestionKey {
  generator: string
  createdAt?: string | null
  id?: string | null
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

function stamp(value: string | null | undefined): number | null {
  if (!value) return null
  const iso = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const ms = Date.parse(iso)
  return Number.isFinite(ms) ? ms : null
}

export function compareQuestions(a: QuestionKey, b: QuestionKey): number {
  const byKind = compareKinds(a.generator, b.generator)
  if (byKind) return byKind
  const at = stamp(a.createdAt)
  const bt = stamp(b.createdAt)
  if (at !== null && bt !== null && at !== bt) return at - bt
  if (a.id && b.id) return cmp(a.id, b.id)
  return 0
}

/** A sorted copy; ties keep the order they came in. */
export function sortQuestions<T>(items: readonly T[], keyOf: (item: T) => QuestionKey): T[] {
  return items
    .map((item, at) => ({ item, at, key: keyOf(item) }))
    .sort((a, b) => compareQuestions(a.key, b.key) || a.at - b.at)
    .map((row) => row.item)
}

/** Kinds in the canonical order; duplicates dropped. */
export function sortKinds(kinds: Iterable<string>): string[] {
  return [...new Set(kinds)].sort(compareKinds)
}
