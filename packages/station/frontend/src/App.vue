<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
import { useTheme } from '@/composables/useTheme'
import 'vue-sonner/style.css'

useTheme()
</script>

<template>
  <div class="flex h-full flex-col bg-background text-foreground">
    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <RouterView />
    </div>
    <Toaster position="top-right" rich-colors close-button />
  </div>
</template>
