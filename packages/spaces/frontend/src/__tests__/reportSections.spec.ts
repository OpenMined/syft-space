import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, defineComponent, h, ref, shallowRef, type Component } from 'vue'
import { mount } from '@vue/test-utils'
import ReportAnswered from '@/components/benchmark/report/ReportAnswered.vue'
import ReportKinds from '@/components/benchmark/report/ReportKinds.vue'
import ReportModels from '@/components/benchmark/report/ReportModels.vue'
import ReportSummary from '@/components/benchmark/report/ReportSummary.vue'
import { provideRun, type RunContext } from '@/components/benchmark/report/context'
import { OPUS, QWEN, runReport } from './reportFixtures'

function fakeRun(model = OPUS) {
  const selected = ref(model)
  const kind = ref<string | null>(null)
  const data = shallowRef(runReport())
  const run = {
    jobId: 'j1',
    data,
    loading: ref(false),
    error: ref<string | null>(null),
    running: computed(() => false),
    model: computed(() => selected.value),
    modelReport: computed(() => data.value.models.find((m) => m.model === selected.value) ?? null),
    selectModel: vi.fn((m: string) => (selected.value = m)),
    kind,
    setKind: vi.fn((k: string | null) => (kind.value = k)),
    reload: vi.fn(async () => {}),
  }
  return run satisfies RunContext
}

function mountSection(section: Component, run: ReturnType<typeof fakeRun>) {
  const Host = defineComponent({
    setup() {
      provideRun(run)
      return () => h(section, { slug: 'ep', jobId: 'j1', modelId: run.model.value })
    },
  })
  return mount(Host, { attachTo: document.body })
}

beforeEach(() => {
  document.body.innerHTML = ''
  Element.prototype.scrollIntoView = vi.fn()
})

describe('ReportSummary', () => {
  it('states the selected model’s figures', () => {
    const wrapper = mountSection(ReportSummary, fakeRun())
    expect(wrapper.get('[data-testid="summary-sentence"]').text().replace(/\s+/g, ' ')).toBe(
      'With your data, Claude Opus 4.8 answered 80% of 100 questions correctly. On its own, with web search, it answered 30%.',
    )
    expect(wrapper.get('[data-testid="tile-with"]').text()).toContain('80%')
    expect(wrapper.get('[data-testid="tile-alone"]').text()).toContain('30%')
    expect(wrapper.get('[data-testid="tile-lift"]').text()).toContain('+50')
    expect(wrapper.get('[data-testid="tile-made-up"]').text().replace(/\s+/g, ' ')).toContain(
      '25% → 8%',
    )
  })

  it('follows the model selection', async () => {
    const run = fakeRun(QWEN)
    const wrapper = mountSection(ReportSummary, run)
    expect(wrapper.get('[data-testid="summary-sentence"]').text()).toContain('Qwen 3.8 27B')
    expect(wrapper.get('[data-testid="tile-lift"]').text()).toContain('+47')
  })
})

describe('ReportModels', () => {
  it('lists every model and selects one on click', async () => {
    const run = fakeRun()
    const wrapper = mountSection(ReportModels, run)
    const rows = wrapper.findAll('[data-testid="model-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.classes()).toContain('bg-primary/5')
    expect(rows[1]!.text()).toContain('+47')
    expect(rows[1]!.text()).toContain('22% → 7%')
    await rows[1]!.get('button').trigger('click')
    expect(run.selectModel).toHaveBeenCalledWith(QWEN)
  })
})

describe('ReportAnswered', () => {
  it('splits both arms into right, didn’t know and made up', () => {
    const wrapper = mountSection(ReportAnswered, fakeRun())
    const alone = wrapper.get('[data-testid="answered-closed"]').text().replace(/\s+/g, ' ')
    expect(alone).toContain('Right 30%')
    expect(alone).toContain('Didn’t know 45%')
    expect(alone).toContain('Made it up 25%')
    const withData = wrapper.get('[data-testid="answered-ctx"]').text().replace(/\s+/g, ' ')
    expect(withData).toContain('Right 80%')
    expect(wrapper.get('[data-testid="answered-left-out"]').text()).toContain('3 not graded yet')
  })
})

describe('ReportKinds', () => {
  it('filters the questions by kind and clears on a second click', async () => {
    const run = fakeRun()
    const wrapper = mountSection(ReportKinds, run)
    const rows = wrapper.findAll('[data-testid="kind-row"]')
    expect(rows[0]!.findAll('td').map((td) => td.text())).toEqual(['Names', '10% → 90%', '+80'])

    await rows[1]!.get('button').trigger('click')
    expect(run.setKind).toHaveBeenLastCalledWith('temporal_masking')
    expect(rows[1]!.get('button').attributes('aria-pressed')).toBe('true')

    await rows[1]!.get('button').trigger('click')
    expect(run.setKind).toHaveBeenLastCalledWith(null)
  })
})
