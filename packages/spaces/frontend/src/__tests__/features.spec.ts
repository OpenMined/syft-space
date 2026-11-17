import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/endpoints/settings', () => ({
  settingsApi: { getFeatures: vi.fn() },
}))

import { settingsApi } from '@/api/endpoints/settings'

// A fresh module per test: the loaded flags are module state.
async function freshFeatures() {
  vi.resetModules()
  return import('@/config/features')
}

describe('feature flags', () => {
  beforeEach(() => {
    vi.mocked(settingsApi.getFeatures).mockReset()
  })

  it('keeps the benchmark hidden until the backend enables it', async () => {
    const { features } = await freshFeatures()

    expect(features.benchmark).toBe(false)
  })

  it('follows the backend', async () => {
    vi.mocked(settingsApi.getFeatures).mockResolvedValue({ benchmark: true })
    const { features, loadFeatures } = await freshFeatures()

    await loadFeatures()

    expect(features.benchmark).toBe(true)
  })

  it('asks the backend once', async () => {
    vi.mocked(settingsApi.getFeatures).mockResolvedValue({ benchmark: true })
    const { loadFeatures } = await freshFeatures()

    await loadFeatures()
    await loadFeatures()

    expect(settingsApi.getFeatures).toHaveBeenCalledTimes(1)
  })

  it('stays hidden and retries after a failed load', async () => {
    vi.mocked(settingsApi.getFeatures)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ benchmark: true })
    const { features, loadFeatures } = await freshFeatures()

    await loadFeatures()
    expect(features.benchmark).toBe(false)

    await loadFeatures()
    expect(features.benchmark).toBe(true)
  })
})
