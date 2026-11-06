import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import RepublishBanner from '@/components/RepublishBanner.vue'
import { toast } from 'vue-sonner'

const api = vi.hoisted(() => ({ publish: vi.fn() }))
vi.mock('@/api/endpoints/endpoints', () => ({ endpointsApi: api }))
vi.mock('vue-sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const search = { slug: 'search', name: 'Podcast search', published_to: ['m1', 'm2'] }
const qa = { slug: 'qa', name: 'News QA' }

const mountBanner = (endpoints = [search, qa], datasetNames = ['Feeds']) =>
  mount(RepublishBanner, { props: { endpoints, datasetNames } })

const buttons = (wrapper: ReturnType<typeof mountBanner>) => ({
  later: wrapper.get('button:nth-of-type(1)'),
  republish: wrapper.get('button:nth-of-type(2)'),
})

beforeEach(() => {
  api.publish.mockReset()
  vi.mocked(toast.success).mockReset()
  vi.mocked(toast.error).mockReset()
})

describe('RepublishBanner', () => {
  it('names the count of APIs and the changed data source', () => {
    expect(mountBanner().text()).toContain('2 published APIs use "Feeds".')
    expect(mountBanner([search]).text()).toContain('One published API uses "Feeds".')
    expect(mountBanner([search], ['A', 'B']).text()).toContain('2 changed data sources.')
  })

  it('renders nothing when there is nothing pending', () => {
    expect(mountBanner([]).text()).toBe('')
  })

  it('republishes each API to where it already is, then clears the pending list', async () => {
    api.publish.mockResolvedValue({})
    const wrapper = mountBanner()
    await buttons(wrapper).republish.trigger('click')
    await flushPromises()

    expect(api.publish.mock.calls).toEqual([
      ['search', { marketplace_ids: ['m1', 'm2'] }],
      ['qa', { publish_to_all_marketplaces: true }],
    ])
    expect(wrapper.emitted('update:endpoints')).toEqual([[[]]])
    expect(toast.success).toHaveBeenCalledWith('2 APIs republished')
  })

  it('keeps only the failed APIs pending and names them', async () => {
    api.publish.mockImplementation(async (slug: string) => {
      if (slug === 'qa') throw new Error('hub down')
      return {}
    })
    const wrapper = mountBanner()
    await buttons(wrapper).republish.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:endpoints')).toEqual([[[qa]]])
    expect(toast.error).toHaveBeenCalledWith('Failed to republish: News QA')
  })

  it('Later dismisses without a request', async () => {
    const wrapper = mountBanner()
    await buttons(wrapper).later.trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
    expect(api.publish).not.toHaveBeenCalled()
  })
})
