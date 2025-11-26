<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'
import { useTheme } from './composables/useTheme'

const route = useRoute()
const showNavbar = computed(() => route.name !== 'create' && !route.path.startsWith('/create/') && route.name !== 'updates')

// Initialize theme support
useTheme()
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <AppNavbar v-if="showNavbar" />

    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped></style>
