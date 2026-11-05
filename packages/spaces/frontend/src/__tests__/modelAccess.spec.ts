import { describe, expect, it } from 'vitest'

import type { ProviderResponse, ProviderRole } from '@/api/types'
import {
  MODEL_ACCESS_ROLES,
  effectiveUrl,
  keySource,
  localityTip,
  type ProviderKey,
} from '@/components/benchmark/modelAccess'

function role(overrides: Partial<ProviderRole> = {}): ProviderRole {
  return {
    url: '',
    url_default: '',
    key_set: false,
    key_updated_at: null,
    local: null,
    ...overrides,
  }
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

describe('localityTip', () => {
  it.each([
    ['benchmark', true, 'Keys go to benchmark, on this machine or its Docker network.'],
    ['bench.example.com', false, 'Keys go to bench.example.com, outside this machine.'],
    ['', true, 'Keys go to the default address, on this machine or its Docker network.'],
  ])('names %s', (where, local, tip) => {
    expect(localityTip(where, local, 'Keys go to')).toBe(tip)
  })
})

describe('effectiveUrl', () => {
  it('takes the shared address when a role is blank', () => {
    expect(effectiveUrl(blank, view(), 'judge')).toBe('http://ollama:11434')
  })

  it('lets the web check follow the models being tested', () => {
    const urls = { ...blank, subject: 'https://openrouter.ai/api/v1' }
    expect(effectiveUrl(urls, view(), 'filter')).toBe('https://openrouter.ai/api/v1')
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

  it('says unknown, never none, when a key it depends on could not be read', () => {
    const v = view({ shared: role({ key_set: null }), subject: role({ key_set: null }) })
    expect(keySource(v, 'shared')).toBe('unknown')
    expect(keySource(v, 'judge')).toBe('unknown')
    expect(keySource(v, 'filter')).toBe('unknown')
  })
})
