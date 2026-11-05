import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ListRowsEditor from '@/components/ListRowsEditor.vue'

const paste = async (separator: string, text: string) => {
  const wrapper = mount(ListRowsEditor, {
    props: { modelValue: ['first'], label: 'URL', separator },
  })
  await wrapper.get('input').trigger('paste', { clipboardData: { getData: () => text } })
  return wrapper.emitted('update:modelValue')?.[0]?.[0]
}

describe('ListRowsEditor paste', () => {
  it('fills one row per separated value and per line', async () => {
    expect(await paste(',', 'https://a/, https://b/\nhttps://c/')).toEqual([
      'https://a',
      'https://b',
      'https://c',
    ])
  })

  it('splits on the literal separator, whatever character it is', async () => {
    expect(await paste(']', 'a]b]c')).toEqual(['a', 'b', 'c'])
    expect(await paste('-', 'x-y')).toEqual(['x', 'y'])
    expect(await paste('\\', 'p\\q')).toEqual(['p', 'q'])
  })

  it('leaves a paste without separators to the browser', async () => {
    expect(await paste(',', 'single-value')).toBeUndefined()
  })
})
