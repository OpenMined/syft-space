import { ref, watch, type Ref } from 'vue'

const KEY = 'benchmark-results-show-combined'

function stored(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

const shown = ref(stored())

watch(shown, (on) => {
  try {
    localStorage.setItem(KEY, on ? '1' : '0')
  } catch {
    // localStorage unavailable: the choice lives in memory.
  }
})

/** Whether the runs list also shows runs that a combined run holds. */
export function useShowCombined(): Ref<boolean> {
  return shown
}
