<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'

defineProps<{
  isSlow: boolean
}>()
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center bg-background text-foreground">
    <h1 class="mb-6 text-2xl font-semibold">Syft Space</h1>
    <Loader2 class="mb-4 h-8 w-8 animate-spin text-muted-foreground" />
    <p class="text-sm text-muted-foreground">Starting up...</p>
    <p v-if="isSlow" class="mt-2 text-xs text-muted-foreground/70">
      This is taking longer than expected...
    </p>
  </div>
</template>
