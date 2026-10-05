import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import type { LocationQuery } from 'vue-router'

const route = reactive<{ query: LocationQuery }>({ query: {} })

vi.mock('vue-router', () => ({ useRoute: () => route }))

function stub(name: string) {
  return defineComponent({
    name,
    props: ['slug', 'jobId', 'modelId'],
    setup: (props) => () => h('div', { 'data-view': name }, JSON.stringify({ ...props })),
  })
}

vi.mock('@/components/BenchmarkResults.vue', () => ({ default: stub('BenchmarkResults') }))
vi.mock('@/components/benchmark/report/RunsList.vue', () => ({ default: stub('RunsList') }))
vi.mock('@/components/benchmark/report/useRunReport', () => ({ useRunReport: () => ({}) }))
vi.mock('@/components/benchmark/report/RunReport.vue', () => ({ default: stub('RunReport') }))

const { default: ResultsHome } = await import('@/components/benchmark/report/ResultsHome.vue')

function shown(wrapper: ReturnType<typeof mount>): {
  name: string
  props: Record<string, unknown>
} {
  const el = wrapper.get('[data-view]')
  return { name: el.attributes('data-view') ?? '', props: JSON.parse(el.text()) }
}

describe('ResultsHome', () => {
  it('switches between the list, the report and the technical view', async () => {
    route.query = { tab: 'results' }
    const wrapper = mount(ResultsHome, { props: { slug: 'ep' } })
    expect(shown(wrapper)).toEqual({ name: 'RunsList', props: { slug: 'ep' } })

    route.query = { tab: 'results', job: 'j1', model: 'm1' }
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual({
      name: 'RunReport',
      props: { slug: 'ep', jobId: 'j1', modelId: 'm1' },
    })

    route.query = { tab: 'results', job: 'j1' }
    await wrapper.vm.$nextTick()
    expect(shown(wrapper).props.modelId).toBeNull()

    route.query = { tab: 'results', view: 'technical', job: 'j1' }
    await wrapper.vm.$nextTick()
    expect(shown(wrapper)).toEqual({ name: 'BenchmarkResults', props: { slug: 'ep' } })
  })
})
