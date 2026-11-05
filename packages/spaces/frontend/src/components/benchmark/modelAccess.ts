/**
 * The Model access roles: what each sends, and where its calls go.
 *
 * Whether an address stays local is decided by the backends, never here: the
 * benchmark for a provider role (`ProviderRole.local`), the Space for its own
 * addresses (`benchmarksApi.locality`).
 */
import type { ProviderResponse } from '@/api/types'

export type ProviderKey = keyof ProviderResponse

export interface ModelAccessRole {
  key: ProviderKey
  label: string
  /** One sentence for the tooltip. */
  tip: string
  /** What the role sends to its provider; empty for the shared default. */
  sends: string
  /** The role whose address a blank one takes. */
  fallback: ProviderKey | null
  /** The credential slot on the benchmark. */
  keyName: string
}

export const MODEL_ACCESS_ROLES: ModelAccessRole[] = [
  {
    key: 'shared',
    label: 'Shared default',
    tip: 'Used by any role left blank.',
    sends: '',
    fallback: null,
    keyName: 'llm_api_key',
  },
  {
    key: 'generator',
    label: 'Question writer',
    tip: 'Reads your articles and writes the questions.',
    sends: 'Full articles',
    fallback: 'shared',
    keyName: 'generator_key',
  },
  {
    key: 'filter',
    label: 'Web check',
    tip: 'Searches the web for each question; blank fields follow Models being tested.',
    sends: 'The questions',
    fallback: 'subject',
    keyName: 'filter_key',
  },
  {
    key: 'subject',
    label: 'Models being tested',
    tip: 'Answer the questions, with and without excerpts from your articles.',
    sends: 'Questions and excerpts',
    fallback: 'shared',
    keyName: 'subject_key',
  },
  {
    key: 'judge',
    label: 'Judges',
    tip: 'Grade each answer; should not share a company with a model being tested.',
    sends: "Question, correct answer and the model's answer",
    fallback: 'shared',
    keyName: 'judge_key',
  },
]

/**
 * One sentence on where an address points, for a locality chip's tooltip.
 *
 * @param where - The address or its host; empty for the default address
 * @param local - Whether it stays local, as a backend judged it
 * @param lead - What reaches it, e.g. "Sent to"
 */
export function localityTip(where: string, local: boolean, lead: string): string {
  const place = where || 'the default address'
  return local
    ? `${lead} ${place}, on this machine or its Docker network.`
    : `${lead} ${place}, outside this machine.`
}

/**
 * The address a role actually calls: its own, else its installation default,
 * else its fallback role's.
 *
 * @param urls - The addresses as typed on the page, by role
 * @param view - What the benchmark reported, for the defaults
 * @param key - The role
 */
export function effectiveUrl(
  urls: Record<ProviderKey, string>,
  view: ProviderResponse,
  key: ProviderKey,
): string {
  const own = urls[key].trim() || view[key].url_default.trim()
  if (own) return own
  const fallback = MODEL_ACCESS_ROLES.find((role) => role.key === key)?.fallback
  return fallback ? effectiveUrl(urls, view, fallback) : ''
}

export type KeySource = 'own' | 'inherited' | 'none' | 'unknown'

/**
 * Whether a role calls with its own key, one it inherits, or none;
 * unknown when a key it depends on could not be read.
 */
export function keySource(view: ProviderResponse, key: ProviderKey): KeySource {
  const keySet = view[key].key_set
  if (keySet) return 'own'
  if (keySet === null) return 'unknown'
  const fallback = MODEL_ACCESS_ROLES.find((role) => role.key === key)?.fallback
  if (!fallback) return 'none'
  const followed = keySource(view, fallback)
  return followed === 'own' ? 'inherited' : followed
}
