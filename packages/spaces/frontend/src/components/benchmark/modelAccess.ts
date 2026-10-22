/**
 * The Model access roles: what each sends, and whether it leaves this machine.
 *
 * The locality rule mirrors the benchmark's perimeter check (`check_model_host`):
 * a loopback name or a dotless Docker service name stays on the machine,
 * anything else leaves it.
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

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '0.0.0.0', 'host.docker.internal'])

/** The host of an address, lower-cased; empty when it cannot be read. */
export function hostOf(url: string): string {
  const text = url.trim()
  if (!text) return ''
  try {
    const parsed = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : `http://${text}`)
    return parsed.hostname.replace(/^\[|\]$/g, '').toLowerCase()
  } catch {
    return ''
  }
}

/** Whether a call to this address stays on this machine. */
export function staysLocal(url: string): boolean {
  const host = hostOf(url)
  return LOCAL_HOSTS.has(host) || !host.includes('.')
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

export type KeySource = 'own' | 'inherited' | 'none'

/** Whether a role calls with its own key, one it inherits, or none. */
export function keySource(view: ProviderResponse, key: ProviderKey): KeySource {
  if (view[key].key_set) return 'own'
  const fallback = MODEL_ACCESS_ROLES.find((role) => role.key === key)?.fallback
  if (!fallback) return 'none'
  return keySource(view, fallback) === 'none' ? 'none' : 'inherited'
}
