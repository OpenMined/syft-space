<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
import DemoBanner from '@/components/DemoBanner.vue'
import { useTheme } from '@/composables/useTheme'
import 'vue-sonner/style.css'

useTheme()
</script>

<template>
  <div class="flex h-screen flex-col bg-background text-foreground">
    <DemoBanner class="shrink-0" />
    <div class="min-h-0 flex-1 overflow-y-auto">
      <RouterView />
    </div>
    <Toaster position="top-right" rich-colors />
  </div>
</template>
