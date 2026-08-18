<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from './components/AppLayout.vue'
import AppTopbar from './components/AppTopbar.vue'
import FeedbackButton from './components/FeedbackButton.vue'
import SplashScreen from './components/SplashScreen.vue'
import { useTheme } from './composables/useTheme'
import { loadGlobalData } from './lib/utils'
import { Toaster } from '@/components/ui/sonner'
import { useServerAvailabilityStore } from '@/stores/serverAvailability'
import 'vue-sonner/style.css'

const route = useRoute()

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
const isAboutPage = computed(() => route.name === 'about')
const isStandalonePage = computed(() => isUpdatesPage.value || isAboutPage.value)

const showSidebar = computed(
  () =>
    route.name !== 'create' &&
    !route.path.startsWith('/create/') &&
    !route.path.startsWith('/go-live') &&
    !route.path.startsWith('/experimental') &&
    !isStandalonePage.value &&
    route.name !== 'onboarding',
)

useTheme()

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
  <SplashScreen v-if="!serverStore.isReady && !isStandalonePage" :is-slow="serverStore.isSlow" />
  <template v-else>
    <!-- Sidebar layout for main app -->
    <AppLayout v-if="showSidebar">
      <router-view />
    </AppLayout>

    <!-- Full-screen layout for standalone/create/onboarding pages -->
    <div v-else class="flex h-screen flex-col bg-background text-foreground">
      <div v-if="!isStandalonePage" class="hidden md:block">
        <AppTopbar />
      </div>
      <div class="flex-1 overflow-y-auto">
        <router-view />
      </div>
    </div>

    <FeedbackButton v-if="!isStandalonePage" />
    <Toaster position="top-center" />
  </template>
</template>
