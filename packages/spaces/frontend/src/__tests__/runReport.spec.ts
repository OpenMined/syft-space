import { describe, expect, it } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import RunReport from '@/components/benchmark/report/RunReport.vue'
import { provideRunReport } from '@/components/benchmark/report/context'
import type { RunReport as RunReportData } from '@/components/benchmark/report/useRunReport'
import { runReport } from './reportFixtures'

describe('RunReport', () => {
  it('shows one short empty state for a model not in the run, whatever the screen', async () => {
    const Host = defineComponent({
      setup() {
        provideRunReport({
          isRunning: () => false,
          loadReport: async () => runReport(),
          revision: ref(0),
          runs: ref([]),
        } as unknown as RunReportData)
        return () =>
          h(RunReport, { slug: 'ep', jobId: 'j1', screen: 'checks', modelId: 'nobody/unknown' })
      },
    })
    const wrapper = mount(Host, { global: { stubs: { RouterLink: RouterLinkStub } } })
    await flushPromises()
    expect(wrapper.get('[data-testid="model-missing"]').text()).toBe(
      'This model is not part of this run.',
    )
    expect(wrapper.find('[data-testid="screen-ChecksPage"]').exists()).toBe(false)
  })
})
