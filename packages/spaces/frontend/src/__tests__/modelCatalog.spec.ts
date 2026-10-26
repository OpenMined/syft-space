import { beforeEach, describe, expect, it, vi } from 'vitest'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { useModelCatalog } from '@/composables/useModelCatalog'
import type { BenchmarkModelCatalog } from '@/api/types'

vi.mock('@/api/endpoints/benchmarks', () => ({
  benchmarksApi: { listModels: vi.fn(), refreshModels: vi.fn() },
}))

const listModels = vi.mocked(benchmarksApi.listModels)
const refreshModels = vi.mocked(benchmarksApi.refreshModels)

const answer = (count: number): BenchmarkModelCatalog => ({
  models: Array.from({ length: count }, (_, index) => ({
    id: `vendor/model-${index}`,
    name: `Model ${index}`,
    vendor: 'vendor',
    build: `vendor/model-${index}-20260101`,
    context_length: 128000,
    max_output_tokens: 8192,
    input_modalities: ['text'],
    supports: ['temperature'],
    pricing: { prompt: '0.000001', completion: '0.000002' },
    retires_on: null,
    routes: {},
    aliases: {},
    source: 'openrouter',
    local: false,
  })),
  vendors: ['vendor'],
  pins: { '~vendor/model-latest': 'vendor/model-0' },
  fetched: { openrouter: '2026-09-20T11:02:57+00:00' },
  total: count,
})

// A fresh connection id per test: the cache is module-level.
let connection = 0
const next = (): string => `connection-${++connection}`

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useModelCatalog', () => {
  it('fetches a connection catalogue once, however many pickers ask', async () => {
    listModels.mockResolvedValue(answer(2))
    const id = next()

    const first = useModelCatalog()
    const second = useModelCatalog()
    await Promise.all([first.load(id), second.load(id)])

    expect(listModels).toHaveBeenCalledTimes(1)
    expect(first.catalog.value.models).toHaveLength(2)
    expect(second.catalog.value.models).toHaveLength(2)
  })

  it('does not hold one benchmark answer for another', async () => {
    listModels.mockResolvedValueOnce(answer(1)).mockResolvedValueOnce(answer(3))

    const one = useModelCatalog()
    await one.load(next())
    const other = useModelCatalog()
    await other.load(next())

    expect(listModels).toHaveBeenCalledTimes(2)
    expect(other.catalog.value.models).toHaveLength(3)
  })

  it('replaces what is held when the benchmark refetches its provider list', async () => {
    // A refresh replaces the list rather than merging into it.
    listModels.mockResolvedValue(answer(2))
    refreshModels.mockResolvedValue(answer(5))
    const id = next()

    const picker = useModelCatalog()
    await picker.load(id)
    expect(await picker.refresh(id)).toBe(true)
    expect(picker.catalog.value.models).toHaveLength(5)

    // The cache holds the new list too.
    const another = useModelCatalog()
    await another.load(id)
    expect(another.catalog.value.models).toHaveLength(5)
    expect(listModels).toHaveBeenCalledTimes(1)
  })

  it('keeps the benchmark own words about a refusal', async () => {
    // The benchmark's own message is shown as is.
    refreshModels.mockRejectedValue({
      response: { data: { detail: 'add openrouter.ai to external_hosts' } },
    })

    const picker = useModelCatalog()
    expect(await picker.refresh(next())).toBe(false)
    expect(picker.error.value).toContain('external_hosts')
  })

  it('survives a benchmark that hands over nothing', async () => {
    // Not fatal: the picker still takes a typed identifier.
    listModels.mockRejectedValue(new Error('benchmark is not answering'))

    const picker = useModelCatalog()
    await picker.load(next())

    expect(picker.catalog.value.models).toEqual([])
    expect(picker.error.value).toContain('not answering')
  })
})
