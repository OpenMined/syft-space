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

// A fresh connection id per test: the cache is module-level on purpose — four
// pickers on one form share it — so reusing an id would leak one test's
// catalogue into the next.
let connection = 0
const next = (): string => `connection-${++connection}`

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useModelCatalog', () => {
  it('fetches a connection catalogue once, however many pickers ask', async () => {
    // Four fields on the settings form pick models. Asking four times over one
    // page is three requests for an answer already in hand.
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
    // A refresh exists to make the old list go away. A merge would keep a model
    // the provider has stopped serving on the list for ever — the one kind of
    // stale entry worse than none, because it looks configured and fails at the
    // first call.
    listModels.mockResolvedValue(answer(2))
    refreshModels.mockResolvedValue(answer(5))
    const id = next()

    const picker = useModelCatalog()
    await picker.load(id)
    expect(await picker.refresh(id)).toBe(true)
    expect(picker.catalog.value.models).toHaveLength(5)

    // And the next picker to open gets the new list, not the cached old one.
    const another = useModelCatalog()
    await another.load(id)
    expect(another.catalog.value.models).toHaveLength(5)
    expect(listModels).toHaveBeenCalledTimes(1)
  })

  it('keeps the benchmark own words about a refusal', async () => {
    // A perimeter that forbids the call names the host to open. That is an
    // instruction to the owner, and replacing it with "something went wrong"
    // leaves them with nothing to act on.
    refreshModels.mockRejectedValue({
      response: { data: { detail: 'add openrouter.ai to external_hosts' } },
    })

    const picker = useModelCatalog()
    expect(await picker.refresh(next())).toBe(false)
    expect(picker.error.value).toContain('external_hosts')
  })

  it('survives a benchmark that hands over nothing', async () => {
    // Without a catalogue the picker still takes a typed identifier, which is
    // where these fields were before one existed. A form that cannot open is a
    // worse answer than a form that cannot suggest.
    listModels.mockRejectedValue(new Error('benchmark is not answering'))

    const picker = useModelCatalog()
    await picker.load(next())

    expect(picker.catalog.value.models).toEqual([])
    expect(picker.error.value).toContain('not answering')
  })
})
