import { ref } from 'vue'
import { useStorage } from '@vueuse/core'

const isCollapsed = useStorage<boolean>('syft-sidebar-collapsed', false)
const isMobileOpen = ref(false)

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
