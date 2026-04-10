import { ref, watch } from 'vue'

const STORAGE_KEY = 'syft-sidebar-collapsed'

const isCollapsed = ref<boolean>(localStorage.getItem(STORAGE_KEY) === 'true')
const isMobileOpen = ref(false)

watch(isCollapsed, (val) => {
  localStorage.setItem(STORAGE_KEY, String(val))
})

export function useSidebar() {
  const toggle = () => {
    isCollapsed.value = !isCollapsed.value
  }

  const collapse = () => {
    isCollapsed.value = true
  }

  const expand = () => {
    isCollapsed.value = false
  }

  const toggleMobile = () => {
    isMobileOpen.value = !isMobileOpen.value
  }

  const closeMobile = () => {
    isMobileOpen.value = false
  }

  return {
    isCollapsed,
    isMobileOpen,
    toggle,
    collapse,
    expand,
    toggleMobile,
    closeMobile,
  }
}
