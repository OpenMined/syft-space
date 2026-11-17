import { ref, watch, type Ref } from 'vue'

const KEY = 'benchmark-results-details'

function stored(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

const details = ref(stored())

watch(details, (on) => {
  try {
    localStorage.setItem(KEY, on ? '1' : '0')
  } catch {
    // localStorage unavailable: the choice lives in memory.
  }
})

/** Whether the results tab shows how the run was made: prompts, replies, filter decisions. */
export function useDetails(): Ref<boolean> {
  return details
}
