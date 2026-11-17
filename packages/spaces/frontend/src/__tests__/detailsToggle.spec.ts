import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DetailsToggle from '@/components/benchmark/report/DetailsToggle.vue'
import { useDetails } from '@/components/benchmark/report/details/useDetails'

describe('DetailsToggle', () => {
  it('switches Details on and remembers it across mounts', async () => {
    const details = useDetails()
    details.value = false
    const wrapper = mount(DetailsToggle)
    const toggle = wrapper.get('[data-testid="details-toggle"]')
    expect(toggle.attributes('aria-checked')).toBe('false')

    await toggle.trigger('click')
    expect(details.value).toBe(true)
    expect(localStorage.getItem('benchmark-results-details')).toBe('1')

    const again = mount(DetailsToggle)
    expect(again.get('[data-testid="details-toggle"]').attributes('aria-checked')).toBe('true')
    details.value = false
  })
})
