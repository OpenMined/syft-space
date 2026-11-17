/** The report's customer wording: verdicts and their pill colours, outcomes and model names. */
import type { BenchmarkBehavior, BenchmarkModel } from '@/api/types'
import { TONE } from '../labels'
import type { Group } from './types'

const VERDICT_LABEL: Record<string, string> = {
  correct: 'Right',
  abstain: 'Didn’t know',
  hallucinate: 'Hallucinated',
  web_sourced: 'From the web',
  incomplete: 'Incomplete',
  pending: 'Not graded yet',
  technical: 'Not measured',
}

export function verdictLabel(verdict: string): string {
  return VERDICT_LABEL[verdict] ?? verdict
}

export const WEB_SOURCED_TIP = 'Stated facts its web search supports.'
export const INCOMPLETE_TIP = 'Left out key facts but stated nothing false.'

const VERDICT_TIP: Record<string, string> = {
  web_sourced: WEB_SOURCED_TIP,
  incomplete: INCOMPLETE_TIP,
}

/** Tooltip of a verdict pill; empty when it needs none. */
export function verdictTip(verdict: string | null | undefined): string {
  return (verdict && VERDICT_TIP[verdict]) || ''
}

/** Pill colours without the border reset, shared by every verdict pill. */
const VERDICT_COLORS: Record<string, string> = {
  correct: 'bg-primary/10 text-primary',
  abstain: TONE.muted,
  hallucinate: TONE.failed,
  web_sourced: TONE.info,
  incomplete: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
}

/** Pill colours of a verdict; muted for one without its own. */
export function verdictColors(verdict: string): string {
  return VERDICT_COLORS[verdict] ?? TONE.muted
}

/** Badge classes for a verdict pill. */
export function verdictTone(verdict: string): string {
  return `border-transparent ${verdictColors(verdict)}`
}

/** Tooltip of a `Searched: no` chip when the API gives no reason. */
export const SEARCH_UNUSED_TIP = 'Asked to search the web, but cited nothing.'

/** Control questions: graded on how the model behaves, not on a right answer. */
const CONTROL_KINDS = new Set(['unanswerable_property', 'false_premise'])

export type Behavior = BenchmarkBehavior

const BEHAVIOR_OF: Record<string, Behavior> = {
  abstain: 'declined',
  correct: 'corrected',
  web_sourced: 'web_sourced',
  hallucinate: 'made_up',
}

/** A control answer's fine outcome: the API's, else derived from the verdict; null otherwise. */
export function behaviorOf(
  generator: string | null | undefined,
  verdict: string | null | undefined,
  given?: string | null,
): Behavior | null {
  if (!generator || !CONTROL_KINDS.has(generator)) return null
  if (given && given in BEHAVIOR_LABEL) return given as Behavior
  return verdict ? (BEHAVIOR_OF[verdict] ?? null) : null
}

export const BEHAVIOR_LABEL: Record<Behavior, string> = {
  declined: 'Declined',
  corrected: 'Corrected',
  web_sourced: 'From the web',
  made_up: 'Hallucinated',
}

/** A verdict in words: the fine outcome on a control question, else the verdict. */
export function outcomeLabel(
  generator: string | null | undefined,
  verdict: string,
  given?: string | null,
): string {
  const behavior = behaviorOf(generator, verdict, given)
  return behavior ? BEHAVIOR_LABEL[behavior] : verdictLabel(verdict)
}

export const GROUP_LABEL: Record<Group, string> = {
  fixed: 'Your data fixed it',
  either: 'Right either way',
  still: 'Still wrong',
  worse: 'Worse with your data',
}

const MODEL_NAME: Record<string, string> = {
  'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
}

const VENDOR_NAME: Record<string, string> = {
  anthropic: 'Anthropic',
  qwen: 'Alibaba',
  'x-ai': 'xAI',
  openai: 'OpenAI',
  google: 'Google',
  'meta-llama': 'Meta',
  mistralai: 'Mistral AI',
  deepseek: 'DeepSeek',
  moonshotai: 'Moonshot AI',
  cohere: 'Cohere',
}

const UPPER = new Set(['gpt', 'glm', 'ai'])

function word(token: string): string {
  if (UPPER.has(token)) return token.toUpperCase()
  if (/^\d+(\.\d+)?[bkm]$/i.test(token)) return token.toUpperCase()
  return token.charAt(0).toUpperCase() + token.slice(1)
}

/**
 * A model's display name: the catalogue entry's, without the vendor the catalogue puts in
 * front (`SpaceXAI: Grok 4.6` → `Grok 4.6`); else one made from the id
 * (`anthropic/claude-opus-4.8` → `Claude Opus 4.8`).
 */
export function modelName(id: string, entry?: Pick<BenchmarkModel, 'name'>): string {
  const name = entry?.name?.trim()
  if (name) {
    const cut = name.indexOf(': ')
    return cut === -1 ? name : name.slice(cut + 2)
  }
  const bare = id.replace(/^~/, '')
  const known = MODEL_NAME[bare]
  if (known) return known
  const tokens = bare
    .slice(bare.lastIndexOf('/') + 1)
    .split(/[-_\s]+/)
    .filter((t) => t && t !== 'preview' && t !== 'latest')
    .flatMap((t) => t.replace(/^([a-z]{2,})(\d)/i, '$1 $2').split(' '))
  if (!tokens.length) return bare
  // `gpt-5.1` keeps its hyphen.
  if (tokens[0]!.toLowerCase() === 'gpt' && tokens.length > 1) {
    return [`GPT-${tokens[1]}`, ...tokens.slice(2).map(word)].join(' ')
  }
  return tokens.map(word).join(' ')
}

/** `Judge 1 (GPT-5.1), Judge 2 (Claude Sonnet 5) and Judge 3 (Gemini 3.1 Pro)`. */
export function judgesText(judges: readonly string[]): string {
  const named = judges.map((j, i) => `Judge ${i + 1} (${modelName(j)})`)
  const last = named.pop()
  if (!last) return ''
  return named.length ? `${named.join(', ')} and ${last}` : last
}

function vendorOf(id: string): string | null {
  const bare = id.replace(/^~/, '')
  const cut = bare.indexOf('/')
  return cut === -1 ? null : bare.slice(0, cut)
}

export function vendorName(id: string): string | null {
  const vendor = vendorOf(id)
  if (!vendor) return null
  return VENDOR_NAME[vendor] ?? vendor.charAt(0).toUpperCase() + vendor.slice(1)
}

export const REMOVED_REASON_LABEL: Record<string, string> = {
  grounding: 'Not supported by the article',
  retrieval_gate: 'Search could not find its passage',
  not_answerable: 'Not answerable from the archive',
  duplicate: 'Duplicate',
  owner: 'Removed by you',
  rotation: 'Rotated out',
  web_answerable: 'Answerable from the web',
  public_knowledge: 'Public knowledge',
  wrong_language: 'Wrong language',
  ambiguous_entity: 'Unclear subject',
  other: 'Other',
}

export function removedReasonLabel(reason: string): string {
  return REMOVED_REASON_LABEL[reason] ?? reason
}
