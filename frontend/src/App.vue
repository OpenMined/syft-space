<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'
import SplashScreen from './components/SplashScreen.vue'
import { useTheme } from './composables/useTheme'
import { loadGlobalData } from './lib/utils'
import { Toaster } from '@/components/ui/sonner'
import { useServerAvailabilityStore } from '@/stores/serverAvailability'
import 'vue-sonner/style.css'

const route = useRoute()
const serverStore = useServerAvailabilityStore()

const showNavbar = computed(
  () =>
    route.name !== 'create' &&
    !route.path.startsWith('/create/') &&
    !route.path.startsWith('/experimental') &&
    route.name !== 'updates' &&
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
  <SplashScreen v-if="!serverStore.isReady" :is-slow="serverStore.isSlow" />
  <div v-else class="min-h-screen bg-background text-foreground">
    <AppNavbar v-if="showNavbar" />

    <main>
      <router-view />
    </main>

    <Toaster position="top-center" />
  </div>
</template>

<style scoped></style>
