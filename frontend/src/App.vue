<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'
import { useTheme } from './composables/useTheme'
import { useUserStore } from './stores/user'
import { Toaster } from '@/components/ui/sonner'
import 'vue-sonner/style.css'

const route = useRoute()
const userStore = useUserStore()

const showNavbar = computed(
  () =>
    route.name !== 'create' &&
    !route.path.startsWith('/create/') &&
    route.name !== 'updates' &&
    route.name !== 'onboarding',
)

// Initialize theme support
useTheme()

// Fetch user data on app load so it's available everywhere
onMounted(() => {
  userStore.fetchMarketplaceInfo()
  userStore.fetchBalance()
})
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <AppNavbar v-if="showNavbar" />

    <main>
      <router-view />
    </main>

    <Toaster position="top-center" />
  </div>
</template>

<style scoped></style>
