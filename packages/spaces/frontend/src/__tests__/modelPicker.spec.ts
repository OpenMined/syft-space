import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'

import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { hintText } from './hint'

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

const FOCUSABLE = 'button, [tabindex]:not([tabindex="-1"])'

describe('ModelPicker chips', () => {
  it('gives each chip one focus stop, its remove button, which names the model id', async () => {
    wrapper = mount(ModelPicker, {
      props: { multiple: true, modelValue: ['openai/gpt-5', 'qwen/qwen3'] },
      attachTo: document.body,
    })
    const chips = wrapper.findAll('[data-slot="badge"]')
    expect(chips).toHaveLength(2)

    const chip = chips[0]!
    expect(chip.attributes('tabindex')).toBeUndefined()
    const stops = chip.findAll(FOCUSABLE)
    expect(stops).toHaveLength(1)
    const remove = stops[0]!
    expect(remove.element.tagName).toBe('BUTTON')
    expect(remove.attributes('tabindex')).toBeUndefined()
    expect(remove.attributes('aria-label')).toBe('Remove GPT-5')
    expect(await hintText(remove)).toBe('Remove openai/gpt-5')
    // Hovering the name shows the id too.
    expect(await hintText(chip.get('span'))).toBe('openai/gpt-5')

    await remove.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[['qwen/qwen3']]])
  })
})
