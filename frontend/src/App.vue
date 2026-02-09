<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'
import SplashScreen from './components/SplashScreen.vue'
import { useTheme } from './composables/useTheme'
import { loadGlobalData } from './lib/utils'
import { Toaster } from '@/components/ui/sonner'
import { useServerAvailabilityStore } from '@/stores/serverAvailability'
import 'vue-sonner/style.css'

const route = useRoute()

// In Tauri, intercept external link clicks and open them in the system browser.
// Uses capture phase so it fires before any @click.stop handlers on individual elements.
const handleExternalLinkClick = (e: MouseEvent) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tauri = (window as any).__TAURI__ as
    | { shell: { open: (url: string) => Promise<void> } }
    | undefined
  if (!tauri) return

  const anchor = (e.target as HTMLElement)?.closest('a')
  if (!anchor) return

  const href = anchor.getAttribute('href')
  if (!href) return

  if (href.startsWith('http://') || href.startsWith('https://')) {
    e.preventDefault()
    e.stopImmediatePropagation()
    tauri.shell.open(href)
  }
}

onMounted(() => {
  document.addEventListener('click', handleExternalLinkClick, true)
})

onUnmounted(() => {
  document.removeEventListener('click', handleExternalLinkClick, true)
})
const serverStore = useServerAvailabilityStore()

const isUpdatesPage = computed(() => route.name === 'updates')

const showNavbar = computed(
  () =>
    route.name !== 'create' &&
    !route.path.startsWith('/create/') &&
    !route.path.startsWith('/experimental') &&
    !isUpdatesPage.value &&
    route.name !== 'onboarding',
)

// Initialize theme support
useTheme()

// Fetch global data once the server is ready
watch(
  () => serverStore.isReady,
  (ready) => {
    if (ready) {
      loadGlobalData()
    }
  },
  { immediate: true },
)
</script>

<template>
  <SplashScreen v-if="!serverStore.isReady && !isUpdatesPage" :is-slow="serverStore.isSlow" />
  <div v-else class="min-h-screen bg-background text-foreground">
    <AppNavbar v-if="showNavbar" />

    <main>
      <router-view />
    </main>

    <Toaster position="top-center" />
  </div>
</template>

<style scoped></style>
