import { describe, expect, it } from 'vitest'

import type { ProviderResponse, ProviderRole } from '@/api/types'
import {
  MODEL_ACCESS_ROLES,
  effectiveUrl,
  hostOf,
  keySource,
  localityTip,
  staysLocal,
  type ProviderKey,
} from '@/components/benchmark/modelAccess'

function role(overrides: Partial<ProviderRole> = {}): ProviderRole {
  return { url: '', url_default: '', key_set: false, key_updated_at: null, ...overrides }
}

function view(overrides: Partial<ProviderResponse> = {}): ProviderResponse {
  return {
    shared: role({ url_default: 'http://ollama:11434' }),
    generator: role(),
    subject: role(),
    judge: role(),
    filter: role(),
    ...overrides,
  }
}

const blank: Record<ProviderKey, string> = {
  shared: '',
  generator: '',
  subject: '',
  judge: '',
  filter: '',
}

describe('model access roles', () => {
  it('lists the four roles after the shared default, in pipeline order', () => {
    expect(MODEL_ACCESS_ROLES.map((r) => r.label)).toEqual([
      'Shared default',
      'Question writer',
      'Web check',
      'Models being tested',
      'Judges',
    ])
  })
})

describe('staysLocal', () => {
  it.each([
    ['http://localhost:11434', true],
    ['http://127.0.0.1:11434/v1', true],
    ['http://[::1]:11434', true],
    ['http://host.docker.internal:11434', true],
    ['http://ollama:11434', true],
    ['localhost:11434', true],
    ['', true],
    ['https://openrouter.ai/api/v1', false],
    ['https://api.openai.com/v1', false],
    ['http://192.168.1.20:11434', false],
  ])('%s -> %s', (url, local) => {
    expect(staysLocal(url)).toBe(local)
  })

  it('reads the host', () => {
    expect(hostOf('https://OpenRouter.ai/api/v1')).toBe('openrouter.ai')
  })
})

describe('localityTip', () => {
  it.each([
    ['http://benchmark:8200', 'Keys go to benchmark, on this machine or its Docker network.'],
    ['http://localhost:8200', 'Keys go to localhost, on this machine or its Docker network.'],
    ['https://bench.example.com', 'Keys go to bench.example.com, outside this machine.'],
    ['http://10.0.0.5:8200', 'Keys go to 10.0.0.5, outside this machine.'],
  ])('names the host of %s', (url, tip) => {
    expect(localityTip(url, 'Keys go to')).toBe(tip)
  })
})

describe('effectiveUrl', () => {
  it('takes the shared address when a role is blank', () => {
    expect(effectiveUrl(blank, view(), 'judge')).toBe('http://ollama:11434')
  })

  it('lets the web check follow the models being tested', () => {
    const urls = { ...blank, subject: 'https://openrouter.ai/api/v1' }
    expect(effectiveUrl(urls, view(), 'filter')).toBe('https://openrouter.ai/api/v1')
    expect(staysLocal(effectiveUrl(urls, view(), 'filter'))).toBe(false)
  })

  it('prefers what is typed over the installation default', () => {
    const urls = { ...blank, generator: 'http://localhost:11434' }
    const v = view({ generator: role({ url_default: 'https://api.openai.com/v1' }) })
    expect(effectiveUrl(urls, v, 'generator')).toBe('http://localhost:11434')
  })
})

describe('keySource', () => {
  it('tells an own key from an inherited one', () => {
    const v = view({ subject: role({ key_set: true }) })
    expect(keySource(v, 'subject')).toBe('own')
    expect(keySource(v, 'filter')).toBe('inherited')
    expect(keySource(v, 'judge')).toBe('none')
  })
})
