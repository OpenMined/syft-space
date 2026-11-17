/** Catalogue models as the setup tab sees them: names, companies, capabilities, picker filters. */
import type { BenchmarkModel, BenchmarkWebSearch } from '@/api/types'

/** Prefixes one company publishes under; mirrors the benchmark's COMPANY_ALIASES. */
const COMPANY_ALIASES: Record<string, string> = {
  'x-ai': 'xai',
  'meta-llama': 'meta',
  mistralai: 'mistral',
  gemini: 'google',
  'bytedance-seed': 'bytedance',
}

const COMPANY_NAMES: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  xai: 'xAI',
  qwen: 'Alibaba',
  deepseek: 'DeepSeek',
  moonshotai: 'Moonshot AI',
  meta: 'Meta',
  mistral: 'Mistral',
  bytedance: 'ByteDance',
}

/** The company behind a model: catalogue vendor, else the id prefix, through the alias map. */
export function companyOf(id: string, vendor?: string): string {
  const raw = (vendor || (id.includes('/') ? id.slice(0, id.indexOf('/')) : '')).toLowerCase()
  return COMPANY_ALIASES[raw] ?? raw
}

export function companyName(company: string): string {
  return COMPANY_NAMES[company] ?? company
}

export interface Clash {
  /** 0-based judge slot. */
  judge: number
  judgeModel: string
  model: string
  company: string
}

/** Every judge paired with a tested model from the same company. */
export function findClashes(
  judges: string[],
  models: string[],
  vendorOf: (id: string) => string | undefined = () => undefined,
): Clash[] {
  const clashes: Clash[] = []
  judges.forEach((judge, index) => {
    if (!judge) return
    const company = companyOf(judge, vendorOf(judge))
    if (!company) return
    for (const model of models) {
      if (companyOf(model, vendorOf(model)) === company) {
        clashes.push({ judge: index, judgeModel: judge, model, company })
      }
    }
  })
  return clashes
}

type CatalogEntry = Pick<BenchmarkModel, 'supports'> & Partial<Pick<BenchmarkModel, 'web_search'>>

export function webSearchOf(entry?: CatalogEntry): BenchmarkWebSearch {
  return entry?.web_search ?? 'none'
}

/** Whether a model takes a temperature; an unknown model is assumed to. */
export function takesTemperature(entry?: CatalogEntry): boolean {
  if (!entry || !entry.supports.length) return true
  return entry.supports.includes('temperature')
}

export type ModelFilter = 'web' | 'no-web' | 'temperature' | 'no-temperature'

export interface ModelFilterChip {
  value: ModelFilter
  label: string
  help: string
}

/** Picker chips. "Web" means built-in search; the plugin works with any OpenRouter model. */
export const MODEL_FILTERS: ModelFilterChip[] = [
  { value: 'web', label: 'Web search', help: 'Models with built-in web search.' },
  { value: 'no-web', label: 'No web search', help: 'Models without built-in web search.' },
  { value: 'temperature', label: 'Temperature', help: 'Models that take a temperature.' },
  { value: 'no-temperature', label: 'No temperature', help: 'Models that take no temperature.' },
]

/** The other chip of the same pair: both of a pair can't be on at once. */
const FILTER_OPPOSITE: Record<ModelFilter, ModelFilter> = {
  web: 'no-web',
  'no-web': 'web',
  temperature: 'no-temperature',
  'no-temperature': 'temperature',
}

export function toggleFilter(on: ModelFilter[], chip: ModelFilter): ModelFilter[] {
  if (on.includes(chip)) return on.filter((item) => item !== chip)
  return [...on.filter((item) => item !== FILTER_OPPOSITE[chip]), chip]
}

export function matchesFilters(entry: CatalogEntry, filters: ModelFilter[]): boolean {
  return filters.every((filter) => {
    switch (filter) {
      case 'web':
        return webSearchOf(entry) === 'native'
      case 'no-web':
        return webSearchOf(entry) !== 'native'
      case 'temperature':
        return takesTemperature(entry)
      case 'no-temperature':
        return !takesTemperature(entry)
    }
  })
}

/** Tested models whose Monte Carlo block is skipped: repeats are on and they take no temperature. */
export function monteCarloSkipped(
  form: { repeat: boolean; models: string[] },
  entryOf: (id: string) => CatalogEntry | undefined,
): string[] {
  if (!form.repeat) return []
  return form.models.filter((id) => !takesTemperature(entryOf(id)))
}

/** A single-model picker's value as one id; '' when empty. */
export function asString(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? '') : (value ?? '')
}

/** A picker's value as a list of ids. */
export function asList(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) return value
  return value ? [value] : []
}
