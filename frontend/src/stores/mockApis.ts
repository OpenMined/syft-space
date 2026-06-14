/**
 * Unified mock APIs store (demo / relationship-facing).
 *
 * An API always sits on top of a single root resource — a Data Source, a Model,
 * or an Agent. It carries policies (here we only track the auto-vs-manual driver,
 * `hasHilPolicy`) and channel bindings that say where it is reachable. This is the
 * single source the Relationships and Triage features read from.
 */
import { reactive } from 'vue'

export type Platform = 'syfthub' | 'slack' | 'whatsapp'
export type RootType = 'data' | 'model' | 'agent'

export interface ChannelBinding {
  platform: Platform
  enabled: boolean
  isDefaultReply: boolean // only meaningful for slack / whatsapp
}

export interface ApiResource {
  id: string
  name: string
  rootType: RootType
  rootResourceId: string
  prompt: string | null
  hasHilPolicy: boolean
  channels: ChannelBinding[]
}

export const PLATFORMS: { id: Platform; label: string }[] = [
  { id: 'syfthub', label: 'SyftHub' },
  { id: 'slack', label: 'Slack' },
  { id: 'whatsapp', label: 'WhatsApp' },
]

export const getPlatformLabel = (id: Platform): string =>
  PLATFORMS.find((p) => p.id === id)?.label ?? id

const emptyChannels = (): ChannelBinding[] =>
  PLATFORMS.map((p) => ({ platform: p.id, enabled: false, isDefaultReply: false }))

export const mockApis = reactive<ApiResource[]>([
  {
    id: 'assistant-api',
    name: 'Personal Assistant API',
    rootType: 'agent',
    rootResourceId: 'personal-assistant',
    prompt: 'You are my personal assistant. Be concise, friendly and proactive.',
    hasHilPolicy: true,
    channels: [
      { platform: 'syfthub', enabled: true, isDefaultReply: false },
      { platform: 'slack', enabled: true, isDefaultReply: true },
      { platform: 'whatsapp', enabled: true, isDefaultReply: true },
    ],
  },
  {
    id: 'research-api',
    name: 'Research Agent API',
    rootType: 'agent',
    rootResourceId: 'research-agent',
    prompt: 'Answer with well-sourced, cited research summaries.',
    hasHilPolicy: false,
    channels: [
      { platform: 'syfthub', enabled: true, isDefaultReply: false },
      { platform: 'slack', enabled: false, isDefaultReply: false },
      { platform: 'whatsapp', enabled: false, isDefaultReply: false },
    ],
  },
  {
    id: 'animals-qa-api',
    name: 'Animals of South Africa Q&A',
    rootType: 'data',
    rootResourceId: 'animals-south-africa',
    prompt: null,
    hasHilPolicy: false,
    channels: emptyChannels(),
  },
])

export interface PlatformDefault {
  platform: Platform
  defaultApiId: string | null
}

export const platformDefaults = reactive<PlatformDefault[]>([
  { platform: 'syfthub', defaultApiId: null },
  { platform: 'slack', defaultApiId: 'assistant-api' },
  { platform: 'whatsapp', defaultApiId: 'assistant-api' },
])

export const getApiById = (apiId: string | null | undefined): ApiResource | undefined =>
  apiId ? mockApis.find((api) => api.id === apiId) : undefined

export const getPlatformDefaultApiId = (platform: Platform): string | null =>
  platformDefaults.find((d) => d.platform === platform)?.defaultApiId ?? null

/**
 * Set the default-reply API for a platform. Clears `isDefaultReply` on every other
 * API's binding for that platform so a platform has at most one default responder.
 */
export const setPlatformDefault = (platform: Platform, apiId: string | null): void => {
  const entry = platformDefaults.find((d) => d.platform === platform)
  if (entry) entry.defaultApiId = apiId

  mockApis.forEach((api) => {
    api.channels.forEach((binding) => {
      if (binding.platform !== platform) return
      binding.isDefaultReply = api.id === apiId
      if (binding.isDefaultReply) binding.enabled = true
    })
  })
}

let apiCounter = 0
export const generateApiId = (): string => `api_${Date.now()}_${apiCounter++}`
