<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

// bg-card, not just the border: in dark mode --border sits one ramp step
// from the page background, so an edge alone is invisible.
// maxHeight bounds a table that grows without limit; the header sticks.
const props = defineProps<{
  class?: HTMLAttributes['class']
  maxHeight?: string
}>()
</script>

<template>
  <div
    data-slot="table-container"
    class="relative w-full overflow-auto rounded-lg border bg-card"
    :style="props.maxHeight ? { maxHeight: props.maxHeight } : undefined"
  >
    <table data-slot="table" :class="cn('w-full caption-bottom text-sm', props.class)">
      <slot />
    </table>
  </div>
</template>
