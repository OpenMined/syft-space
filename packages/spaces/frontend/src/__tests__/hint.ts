import { flushPromises, type DOMWrapper } from '@vue/test-utils'

/**
 * Opens the Hint on `trigger` by hover and returns its text; closes it again. A focus event alone
 * does not open it: Hint opens on keyboard focus only (`:focus-visible`).
 */
export async function hintText(
  trigger: Pick<DOMWrapper<Element>, 'trigger'>,
): Promise<string | undefined> {
  await trigger.trigger('pointermove')
  // The open is scheduled with the provider's zero delay.
  await new Promise((resolve) => setTimeout(resolve, 0))
  await flushPromises()
  const shown = document.body.querySelectorAll('[data-testid="hint"]')
  // The content repeats its text in a visually hidden `role="tooltip"` copy for screen readers.
  const text = shown[shown.length - 1]?.querySelector('[role="tooltip"]')?.textContent ?? undefined
  await trigger.trigger('blur')
  await flushPromises()
  return text
}
