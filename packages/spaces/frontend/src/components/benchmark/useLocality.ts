/** Where an address typed into a form points, as the Space backend judges it. */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { AddressLocality } from '@/api/types'

/** How long typing pauses before the address is asked about. */
export const LOCALITY_DELAY_MS = 300

/**
 * The locality of the address `source` returns, re-asked a moment after it changes.
 *
 * `locality` is the verdict on the text currently returned by `source`, and null while
 * that text is blank, not yet asked about, or could not be asked about. `check` asks at
 * once, for a decision that must not wait for the delay.
 */
export function useLocality(source: () => string) {
  /** The latest answer, with the address it is about. */
  const answer = ref<{ url: string; found: AddressLocality | null } | null>(null)
  const locality = computed(() =>
    answer.value?.url === source().trim() ? answer.value.found : null,
  )
  let latest = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  async function check(url: string): Promise<AddressLocality | null> {
    clearTimeout(timer)
    const ask = ++latest
    const text = url.trim()
    let found: AddressLocality | null = null
    if (text) {
      try {
        found = await benchmarksApi.locality(text)
      } catch {
        found = null
      }
    }
    // A slower answer about an earlier value must not overwrite a newer one.
    if (ask === latest) answer.value = { url: text, found }
    return found
  }

  watch(source, (url) => {
    clearTimeout(timer)
    timer = setTimeout(() => void check(url), LOCALITY_DELAY_MS)
  })
  onBeforeUnmount(() => clearTimeout(timer))

  return { locality, check }
}
