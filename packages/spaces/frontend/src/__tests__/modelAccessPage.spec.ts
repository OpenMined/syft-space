import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import ModelAccessPage from '@/pages/ModelAccessPage.vue'

vi.mock('@/api/endpoints/benchmarks', () => ({
  benchmarksApi: {
    listConnections: vi.fn().mockResolvedValue([]),
    connect: vi.fn().mockResolvedValue({}),
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
    document.body.innerHTML = ''
  })

  it('shows where the benchmark URL points while typing', async () => {
    const wrapper = await mountForm()
    const chip = () =>
      wrapper.get('#bm-url').element.parentElement!.querySelector('[data-testid="locality"]')
    expect(chip()).toBeNull()

    await wrapper.get('#bm-url').setValue('http://benchmark:8200')
    expect(chip()?.textContent).toContain('Stays local')

    await wrapper.get('#bm-url').setValue('https://bench.example.com')
    expect(chip()?.textContent).toContain('Leaves machine')
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
})
