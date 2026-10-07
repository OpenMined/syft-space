import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({ apiClient: { get: vi.fn() } }))

import { apiClient } from '@/api/client'
import { benchmarksApi } from '@/api/endpoints/benchmarks'

const get = vi.mocked(apiClient.get)

describe('benchmarksApi.getWindow', () => {
  beforeEach(() => {
    get.mockReset()
    get.mockResolvedValue({ data: { count: 4, undated: 1, total: 9, window_days: 1 } })
  })

  it('counts with the window on the page', async () => {
    const found = await benchmarksApi.getWindow('atlantic', 1)
    expect(get).toHaveBeenCalledWith('/benchmarks/endpoints/atlantic/window', {
      params: { days: 1 },
    })
    expect(found.count).toBe(4)
  })

  it('leaves the window to the saved one when none is given', async () => {
    await benchmarksApi.getWindow('atlantic')
    expect(get).toHaveBeenCalledWith('/benchmarks/endpoints/atlantic/window', {
      params: undefined,
    })
  })
})
