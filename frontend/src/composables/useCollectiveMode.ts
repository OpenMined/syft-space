import { computed, ref } from 'vue'

// Collective mode is booted via the `?collective=` query param:
//   ?collective=collective-a  -> admin (runs the collective infrastructure)
//   ?collective=collective-m  -> member (virtual space inside a collective)
export type CollectiveMode = 'collective-a' | 'collective-m'
export type CollectiveRole = 'admin' | 'member'
export type CollectiveView = 'collective' | 'personal'

const STORAGE_KEY = 'syft-space-collective-mode'
const VIEW_STORAGE_KEY = 'syft-space-collective-view'

const readStoredMode = (): CollectiveMode | null => {
  if (typeof window === 'undefined') return null
  const value = window.sessionStorage.getItem(STORAGE_KEY)
  return value === 'collective-a' || value === 'collective-m' ? value : null
}

const collectiveMode = ref<CollectiveMode | null>(readStoredMode())

const readStoredView = (): CollectiveView | null => {
  if (typeof window === 'undefined') return null
  const value = window.sessionStorage.getItem(VIEW_STORAGE_KEY)
  return value === 'collective' || value === 'personal' ? value : null
}

const collectiveView = ref<CollectiveView>(readStoredView() ?? 'collective')

// In-memory only (not persisted): the member login gate reappears on every
// fresh page load of `?collective=collective-m`.
const memberLoggedIn = ref<boolean>(false)

const parseCollectiveMode = (value: unknown): CollectiveMode | null => {
  const rawValue = Array.isArray(value) ? value[0] : value
  return rawValue === 'collective-a' || rawValue === 'collective-m' ? rawValue : null
}

export const initializeCollectiveMode = (value: unknown): boolean => {
  const mode = parseCollectiveMode(value)
  if (!mode) return false

  collectiveMode.value = mode
  if (typeof window !== 'undefined') {
    window.sessionStorage.setItem(STORAGE_KEY, mode)
  }

  return true
}

const persistCollectiveView = (view: CollectiveView) => {
  if (typeof window !== 'undefined') {
    window.sessionStorage.setItem(VIEW_STORAGE_KEY, view)
  }
}

const logInMember = () => {
  memberLoggedIn.value = true
}

export function useCollectiveMode() {
  const isCollectiveAdmin = computed(() => collectiveMode.value === 'collective-a')
  const isCollectiveMember = computed(() => collectiveMode.value === 'collective-m')
  const isCollectiveViewActive = computed(
    () => isCollectiveAdmin.value && collectiveView.value === 'collective',
  )
  const isPersonalViewActive = computed(
    () => !isCollectiveAdmin.value || collectiveView.value === 'personal',
  )

  const toggleCollectiveView = () => {
    if (!isCollectiveAdmin.value) return
    const nextView: CollectiveView =
      collectiveView.value === 'collective' ? 'personal' : 'collective'
    collectiveView.value = nextView
    persistCollectiveView(nextView)
  }

  const collectiveBadgeLabel = computed(() =>
    collectiveView.value === 'collective' ? 'Collective' : 'Personal',
  )

  const collectiveRole = computed<CollectiveRole | null>(() => {
    if (isCollectiveAdmin.value) return 'admin'
    if (isCollectiveMember.value) return 'member'
    return null
  })

  const needsMemberLogin = computed(() => isCollectiveMember.value && !memberLoggedIn.value)

  return {
    collectiveMode,
    collectiveView,
    collectiveRole,
    isCollectiveAdmin,
    isCollectiveMember,
    isCollectiveViewActive,
    isPersonalViewActive,
    toggleCollectiveView,
    collectiveBadgeLabel,
    isMemberLoggedIn: computed(() => memberLoggedIn.value),
    needsMemberLogin,
    logInMember,
  }
}
