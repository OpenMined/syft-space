import { reactive, watch } from 'vue'

/**
 * Which collapsible sections of a page are open, remembered per browser.
 *
 * A reload should not put every section back to its default — the owner
 * opened them on purpose. Stored under `storageKey` so two endpoints, or
 * two different pages, keep their own layout rather than sharing one.
 */
export function usePersistedSections(
  storageKey: string,
  defaults: Record<string, boolean>,
): Record<string, boolean> {
  const state = reactive({ ...defaults })
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw) Object.assign(state, JSON.parse(raw))
  } catch {
    // Private window, cleared site data, storage disabled — the defaults
    // stand, and the page still renders correctly without them.
  }
  watch(
    state,
    () => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(state))
      } catch {
        // Storage full or blocked — nothing carries over to the next visit,
        // which is not worse than what a page without this composable does.
      }
    },
    { deep: true },
  )
  return state
}
