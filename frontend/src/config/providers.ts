export interface ProviderConfig {
  id: string
  label: string
  baseUrl: string
}

export const PROVIDERS: ProviderConfig[] = [
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { id: 'groq', label: 'Groq', baseUrl: 'https://api.groq.com/openai/v1' },
  { id: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1' },
  { id: 'together', label: 'Together AI', baseUrl: 'https://api.together.xyz/v1' },
  { id: 'perplexity', label: 'Perplexity', baseUrl: 'https://api.perplexity.ai' },
  { id: 'custom', label: 'Custom / OpenAI-Compatible', baseUrl: '' },
]

const PROVIDER_MAP = Object.fromEntries(PROVIDERS.map((p) => [p.id, p])) as Record<
  string,
  ProviderConfig
>

export function getProviderLabel(providerId: string): string {
  return PROVIDER_MAP[providerId]?.label ?? providerId
}

export function getProviderBaseUrl(providerId: string): string {
  return PROVIDER_MAP[providerId]?.baseUrl ?? ''
}
