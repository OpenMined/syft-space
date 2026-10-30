import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import Hint from '@/components/benchmark/Hint.vue'
import InfoTip from '@/components/benchmark/InfoTip.vue'
import { TooltipProvider } from '@/components/ui/tooltip'
import { hintText } from './hint'

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function shown(): string[] {
  return [...document.body.querySelectorAll('[data-testid="hint"] [role="tooltip"]')].map(
    (el) => el.textContent ?? '',
  )
}

function hinted(slot: () => ReturnType<typeof h>, props: Record<string, unknown> = {}) {
  wrapper = mount(Hint, {
    props: { text: 'Why.', ...props },
    slots: { default: slot },
    attachTo: document.body,
  })
  return wrapper
}

async function tap(el: Element): Promise<void> {
  el.dispatchEvent(
    Object.assign(new Event('pointerdown', { bubbles: true }), { pointerType: 'touch' }),
  )
  document.dispatchEvent(new Event('pointerup'))
  el.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

describe('Hint', () => {
  it('makes a plain element focusable and opens on hover', async () => {
    const w = hinted(() => h('dt', { 'data-testid': 'term' }, 'Written'))
    const term = w.get('[data-testid="term"]')
    expect(term.attributes('tabindex')).toBe('0')
    expect(await hintText(term)).toBe('Why.')
  })

  it('stays closed on a focus that is not :focus-visible', async () => {
    // Such as a dialog focusing its first focusable element after a click.
    const w = hinted(() => h('dt', { 'data-testid': 'term' }, 'Written'))
    await w.get('[data-testid="term"]').trigger('focus')
    expect(shown()).toEqual([])
  })

  it('leaves an element with its own controls out of the tab order', () => {
    const w = hinted(
      () => h('label', { 'data-testid': 'box' }, [h('input', { type: 'checkbox' })]),
      {
        focusable: false,
      },
    )
    expect(w.get('[data-testid="box"]').attributes('tabindex')).toBeUndefined()
  })

  it('renders the element alone without a text', () => {
    const w = hinted(() => h('span', { 'data-testid': 'bare' }, 'x'), { text: null })
    expect(w.get('[data-testid="bare"]').attributes('tabindex')).toBeUndefined()
  })

  it('toggles on a tap', async () => {
    const w = hinted(() => h('span', { 'data-testid': 'chip' }, 'cut'))
    const chip = w.get('[data-testid="chip"]').element
    await tap(chip)
    expect(shown()).toEqual(['Why.'])
    await tap(chip)
    expect(shown()).toEqual([])
  })

  it('leaves a tap on a control inside the element to the control', async () => {
    const w = hinted(() => h('li', [h('span', 'text'), h('button', { type: 'button' }, 'open')]), {
      focusable: false,
    })
    await tap(w.get('button').element)
    expect(shown()).toEqual([])
    await tap(w.get('span').element)
    expect(shown()).toEqual(['Why.'])
  })

  it('works under the app-level provider', async () => {
    const Host = defineComponent({
      setup: () => () =>
        h(TooltipProvider, () =>
          h(Hint, { text: 'Shared.' }, () => h('p', { 'data-testid': 'p' }, 'x')),
        ),
    })
    wrapper = mount(Host, { attachTo: document.body })
    expect(await hintText(wrapper.get('[data-testid="p"]'))).toBe('Shared.')
  })
})

describe('InfoTip', () => {
  it('is an (i) button with the text as its tooltip', async () => {
    wrapper = mount(InfoTip, { props: { text: 'One line.' }, attachTo: document.body })
    const button = wrapper.get('button')
    expect(button.attributes('aria-label')).toBe('One line.')
    expect(await hintText(button)).toBe('One line.')
  })
})
