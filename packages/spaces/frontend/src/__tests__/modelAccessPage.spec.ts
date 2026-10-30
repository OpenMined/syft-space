import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { LOCALITY_DELAY_MS } from '@/components/benchmark/useLocality'
import ModelAccessPage from '@/pages/ModelAccessPage.vue'

// What the Space backend answers; the page applies no rule of its own.
const PLACES: Record<string, { host: string; local: boolean }> = {
  'http://benchmark:8200': { host: 'benchmark', local: true },
  'http://localhost:8200': { host: 'localhost', local: true },
  'http://space:8081': { host: 'space', local: true },
  'https://bench.example.com': { host: 'bench.example.com', local: false },
}

vi.mock('@/api/endpoints/benchmarks', () => ({
  benchmarksApi: {
    listConnections: vi.fn().mockResolvedValue([]),
    connect: vi.fn().mockResolvedValue({}),
    locality: vi.fn(async (url: string) => PLACES[url] ?? { host: '', local: false }),
  },
}))

vi.mock('@/api/endpoints/settings', () => ({
  settingsApi: { getPublicUrl: vi.fn().mockResolvedValue({ public_url: 'http://space:8081' }) },
}))

async function mountForm() {
  const wrapper = mount(ModelAccessPage, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  await flushPromises()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.get('#bm-name').setValue('Bench')
  return wrapper
}

function connectButton(wrapper: Awaited<ReturnType<typeof mountForm>>) {
  return wrapper.findAll('button').find((b) => b.text() === 'Connect')!
}

describe('ModelAccessPage connection URL', () => {
  afterEach(() => {
    vi.mocked(benchmarksApi.connect).mockClear()
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('shows where the benchmark URL points, as the Space says, once typing pauses', async () => {
    const wrapper = await mountForm()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const chip = () =>
      wrapper.get('#bm-url').element.parentElement!.querySelector('[data-testid="locality"]')
    expect(chip()).toBeNull()

    await wrapper.get('#bm-url').setValue('http://benchmark:8200')
    expect(chip()).toBeNull()
    await vi.advanceTimersByTimeAsync(LOCALITY_DELAY_MS)
    await flushPromises()
    expect(benchmarksApi.locality).toHaveBeenLastCalledWith('http://benchmark:8200')
    expect(chip()?.textContent).toContain('Stays local')

    await wrapper.get('#bm-url').setValue('https://bench.example.com')
    await vi.advanceTimersByTimeAsync(LOCALITY_DELAY_MS)
    await flushPromises()
    expect(chip()?.textContent).toContain('Leaves machine')
    wrapper.unmount()
  })

  it('shows no verdict while the new address waits for one, or when it cannot get one', async () => {
    const wrapper = await mountForm()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const chip = () =>
      wrapper.get('#bm-url').element.parentElement!.querySelector('[data-testid="locality"]')

    await wrapper.get('#bm-url').setValue('http://benchmark:8200')
    await vi.advanceTimersByTimeAsync(LOCALITY_DELAY_MS)
    await flushPromises()
    expect(chip()?.textContent).toContain('Stays local')

    // During the typing pause.
    await wrapper.get('#bm-url').setValue('https://bench.example.com')
    expect(chip()).toBeNull()

    // While the request is in flight.
    let answer!: (value: { host: string; local: boolean }) => void
    vi.mocked(benchmarksApi.locality).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve)),
    )
    await vi.advanceTimersByTimeAsync(LOCALITY_DELAY_MS)
    await flushPromises()
    expect(chip()).toBeNull()
    answer(PLACES['https://bench.example.com']!)
    await flushPromises()
    expect(chip()?.textContent).toContain('Leaves machine')

    // After a failed request. Keyed by address: the Space address field asks too.
    vi.mocked(benchmarksApi.locality).mockImplementation(async (url: string) => {
      if (url === 'http://localhost:8200') throw new Error('down')
      return PLACES[url] ?? { host: '', local: false }
    })
    await wrapper.get('#bm-url').setValue('http://localhost:8200')
    await vi.advanceTimersByTimeAsync(LOCALITY_DELAY_MS)
    await flushPromises()
    expect(benchmarksApi.locality).toHaveBeenLastCalledWith('http://localhost:8200')
    expect(chip()).toBeNull()
    vi.mocked(benchmarksApi.locality).mockImplementation(
      async (url: string) => PLACES[url] ?? { host: '', local: false },
    )
    wrapper.unmount()
  })

  it('connects to a local benchmark without asking', async () => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue('http://localhost:8200')
    await connectButton(wrapper).trigger('click')
    await flushPromises()
    expect(benchmarksApi.connect).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('asks before sending keys to a benchmark off this machine', async () => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue('https://bench.example.com')
    await connectButton(wrapper).trigger('click')
    await flushPromises()
    expect(benchmarksApi.connect).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(
      'The control key and provider keys will be sent to bench.example.com.',
    )

    const confirm = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="confirm-remote"]',
    )!
    confirm.click()
    await flushPromises()
    expect(benchmarksApi.connect).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('connects once when Connect is clicked again during the check', async () => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue('http://localhost:8200')
    let answer!: (value: { host: string; local: boolean }) => void
    vi.mocked(benchmarksApi.locality).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve)),
    )

    await connectButton(wrapper).trigger('click')
    expect(connectButton(wrapper).attributes('disabled')).toBeDefined()
    connectButton(wrapper).element.click()
    answer(PLACES['http://localhost:8200']!)
    await flushPromises()

    expect(benchmarksApi.connect).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it.each([
    ['http://localhost:8200', 'local'],
    ['https://bench.example.com', 'remote'],
  ])('drops the check of %s (%s) when the form is cancelled meanwhile', async (address) => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue(address)
    let answer!: (value: { host: string; local: boolean }) => void
    vi.mocked(benchmarksApi.locality).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve)),
    )

    await connectButton(wrapper).trigger('click')
    const cancel = wrapper.findAll('button').find((b) => b.text() === 'Cancel')!
    expect(cancel.attributes('disabled')).toBeUndefined()
    await cancel.trigger('click')
    answer(PLACES[address]!)
    await flushPromises()

    expect(benchmarksApi.connect).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toContain('will be sent to')
    wrapper.unmount()
  })

  it('does not hold a reopened form behind the check the cancelled one left running', async () => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue('http://localhost:8200')
    let answer!: (value: { host: string; local: boolean }) => void
    vi.mocked(benchmarksApi.locality).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve)),
    )
    await connectButton(wrapper).trigger('click')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Cancel')!
      .trigger('click')

    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('#bm-name').setValue('Bench')
    await wrapper.get('#bm-url').setValue('http://benchmark:8200')
    expect(connectButton(wrapper).attributes('disabled')).toBeUndefined()
    await connectButton(wrapper).trigger('click')
    await flushPromises()
    expect(benchmarksApi.connect).toHaveBeenCalledOnce()

    answer(PLACES['http://localhost:8200']!)
    await flushPromises()
    expect(benchmarksApi.connect).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('checks a URL changed during the check before sending keys to it', async () => {
    const wrapper = await mountForm()
    await wrapper.get('#bm-url').setValue('http://localhost:8200')
    let answer!: (value: { host: string; local: boolean }) => void
    vi.mocked(benchmarksApi.locality).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve)),
    )

    await connectButton(wrapper).trigger('click')
    await wrapper.get('#bm-url').setValue('https://bench.example.com')
    answer(PLACES['http://localhost:8200']!)
    await flushPromises()

    expect(benchmarksApi.connect).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(
      'The control key and provider keys will be sent to bench.example.com.',
    )
    document.body.querySelector<HTMLButtonElement>('[data-testid="confirm-remote"]')!.click()
    await flushPromises()
    expect(benchmarksApi.connect).toHaveBeenCalledWith(
      expect.objectContaining({ url: 'https://bench.example.com' }),
    )
    wrapper.unmount()
  })
})
