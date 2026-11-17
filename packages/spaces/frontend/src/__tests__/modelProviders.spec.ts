import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { ProviderKeyState, ProviderResponse, ProviderRole } from '@/api/types'

vi.mock('@/api/endpoints/benchmarks', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  benchmarksApi: {
    getProvider: vi.fn(),
    saveProvider: vi.fn(),
    saveProviderCredential: vi.fn(),
    deleteProviderCredential: vi.fn(),
  },
}))
vi.mock('vue-sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const { benchmarksApi } = await import('@/api/endpoints/benchmarks')
const api = vi.mocked(benchmarksApi)
const { default: ModelProviders } = await import('@/components/benchmark/ModelProviders.vue')

function role(
  url: string,
  keySet: boolean | null = false,
  local: boolean | null = null,
): ProviderRole {
  return { url, url_default: '', key_set: keySet, key_updated_at: null, local }
}

function keyState(keySet: boolean): ProviderKeyState {
  return { key_set: keySet, key_updated_at: keySet ? '2026-10-29T10:00:00Z' : null }
}

function stored(over: Partial<ProviderResponse> = {}): ProviderResponse {
  return {
    shared: role('https://openrouter.ai/api/v1'),
    generator: role(''),
    subject: role(''),
    judge: role(''),
    filter: role(''),
    ...over,
  }
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.clearAllMocks()
})

/** The address boxes in role order: shared, generator, filter, subject, judge. */
function addresses(): HTMLInputElement[] {
  return wrapper!
    .findAll('input')
    .map((i) => i.element as HTMLInputElement)
    .filter((i) => i.type !== 'password')
}

function addressBox(index: number) {
  return wrapper!.findAll('input:not([type="password"])')[index]!
}

async function saveAddresses(): Promise<void> {
  await wrapper!
    .findAll('button')
    .find((b) => b.text() === 'Save addresses')!
    .trigger('click')
  await flushPromises()
}

describe('ModelProviders', () => {
  it('keeps every unsaved address, the key’s own role included, when a key changes', async () => {
    api.getProvider.mockResolvedValue(stored())
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()

    const [, generator, , , judge] = wrapper.findAll('input:not([type="password"])')
    await generator!.setValue('http://ollama:11434')
    await judge!.setValue('https://judge.example/v1')
    api.saveProviderCredential.mockResolvedValue(keyState(true))
    const [, , , , judgeKey] = wrapper.findAll('input[type="password"]')
    await judgeKey!.setValue('sk-judge')
    const save = wrapper.findAll('button').find((b) => b.text() === 'Save')!
    await save.trigger('click')
    await flushPromises()

    expect(api.saveProviderCredential).toHaveBeenCalledWith('c1', 'judge_key', 'sk-judge')
    const values = addresses().map((i) => i.value)
    expect(values[1]).toBe('http://ollama:11434')
    expect(values[4]).toBe('https://judge.example/v1')
    expect(wrapper.text()).toContain('Unsaved changes')

    api.deleteProviderCredential.mockResolvedValue(keyState(false))
    const clear = wrapper.findAll('button').find((b) => b.text() === 'Clear')!
    await clear.trigger('click')
    await flushPromises()
    expect(api.deleteProviderCredential).toHaveBeenCalledWith('c1', 'judge_key')
    expect(addresses().map((i) => i.value)).toEqual([
      'https://openrouter.ai/api/v1',
      'http://ollama:11434',
      '',
      '',
      'https://judge.example/v1',
    ])
    expect(wrapper.text()).toContain('Unsaved changes')
  })

  it('labels each role as the benchmark judged its saved address', async () => {
    api.getProvider.mockResolvedValue(
      stored({
        shared: role('https://openrouter.ai/api/v1', false, false),
        generator: role('http://ollama:11434', false, true),
        subject: role('', false, false),
        judge: role('', false, false),
        filter: role('', false, false),
      }),
    )
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()
    const chips = () => wrapper!.findAll('[data-testid="locality"]').map((c) => c.text())

    // The shared default sends nothing itself and has no chip.
    expect(chips()).toEqual(['Stays local', 'Leaves machine', 'Leaves machine', 'Leaves machine'])
    // The host sits in a tooltip, so the chip takes keyboard focus.
    expect(wrapper.get('[data-testid="locality"]').attributes('tabindex')).toBe('0')

    // An unsaved address has not been judged: its role, and the roles that follow it, lose the chip.
    const [, , , subject] = wrapper.findAll('input:not([type="password"])')
    await subject!.setValue('http://ollama:11434')
    expect(chips()).toEqual(['Stays local', 'Leaves machine'])
  })

  it('keeps a typed key in its box until the benchmark stores it', async () => {
    api.getProvider.mockResolvedValue(stored())
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()
    const judgeKey = () => wrapper!.findAll('input[type="password"]')[4]!
    const save = () => wrapper!.findAll('button').find((b) => b.text() === 'Save')!

    await judgeKey().setValue('sk-judge')
    api.saveProviderCredential.mockRejectedValueOnce(new Error('refused'))
    await save().trigger('click')
    await flushPromises()
    expect((judgeKey().element as HTMLInputElement).value).toBe('sk-judge')

    api.saveProviderCredential.mockResolvedValueOnce(keyState(true))
    await save().trigger('click')
    await flushPromises()
    expect((judgeKey().element as HTMLInputElement).value).toBe('')
  })

  it('keeps each role busy until its own key save ends', async () => {
    api.getProvider.mockResolvedValue(stored())
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()
    const keys = () => wrapper!.findAll('input[type="password"]')
    const answers: Array<(value: ProviderKeyState) => void> = []
    api.saveProviderCredential.mockImplementation(
      () => new Promise((resolve) => answers.push(resolve)),
    )

    for (const index of [1, 4]) {
      await keys()[index]!.setValue('sk-key')
      const rowSave = keys()[index]!.element.parentElement!.querySelector('button')!
      rowSave.click()
      await flushPromises()
    }
    expect(answers).toHaveLength(2)

    answers[0]!(keyState(true))
    await flushPromises()
    expect(keys()[1]!.attributes('disabled')).toBeUndefined()
    expect(keys()[4]!.attributes('disabled')).toBeDefined()

    answers[1]!(keyState(true))
    await flushPromises()
    expect(keys()[4]!.attributes('disabled')).toBeUndefined()
  })

  it('takes key state only from key replies, even when an address save lands later', async () => {
    api.getProvider.mockResolvedValue(stored())
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()
    let answerAddresses: (value: ProviderResponse) => void = () => {}
    api.saveProvider.mockImplementation(() => new Promise((resolve) => (answerAddresses = resolve)))
    await addressBox(4).setValue('https://judge.example/v1')
    await saveAddresses()

    // A key is stored while the address save is still out.
    api.saveProviderCredential.mockResolvedValue(keyState(true))
    await wrapper.findAll('input[type="password"]')[4]!.setValue('sk-judge')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Save')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text().match(/Key set/g)).toHaveLength(1)

    // The address reply was read before the key was stored.
    answerAddresses(stored({ judge: role('https://judge.example/v1', false) }))
    await flushPromises()

    expect(wrapper.text().match(/Key set/g)).toHaveLength(1)
    expect(addresses()[4]!.value).toBe('https://judge.example/v1')
    expect(wrapper.text()).not.toContain('Unsaved changes')
  })

  it('keeps an address typed while the save was in flight', async () => {
    api.getProvider.mockResolvedValue(stored())
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()
    let answerAddresses: (value: ProviderResponse) => void = () => {}
    api.saveProvider.mockImplementation(() => new Promise((resolve) => (answerAddresses = resolve)))
    await addressBox(1).setValue('  http://ollama:11434 ')
    await addressBox(4).setValue('https://judge.example/v1')
    await saveAddresses()

    await addressBox(4).setValue('https://newer.example/v1')
    answerAddresses(
      stored({
        generator: role('http://ollama:11434'),
        judge: role('https://judge.example/v1'),
      }),
    )
    await flushPromises()

    // An untouched box shows what was stored; the edited one keeps the newer text.
    expect(addresses()[1]!.value).toBe('http://ollama:11434')
    expect(addresses()[4]!.value).toBe('https://newer.example/v1')
    expect(wrapper.text()).toContain('Unsaved changes')
  })

  it('claims no key when the benchmark’s keys could not be read', async () => {
    api.getProvider.mockResolvedValue(
      stored({
        shared: role('https://openrouter.ai/api/v1', null),
        generator: role('', null),
        subject: role('', null),
        judge: role('', null),
        filter: role('', null),
      }),
    )
    wrapper = mount(ModelProviders, { props: { connectionId: 'c1' } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('No key')
    expect(wrapper.text().match(/Key unknown/g)).toHaveLength(5)
    // Clearing a key that may not exist would only be refused.
    expect(wrapper.findAll('button').filter((b) => b.text() === 'Clear')).toHaveLength(0)
  })
})
