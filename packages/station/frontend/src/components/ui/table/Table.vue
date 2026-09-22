<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

/**
 * The container is the table's boundary — with several tables on a page, a
 * heading alone doesn't separate them. It carries the card surface as well
 * as the border: in dark mode --border sits one ramp step from the page
 * background, so an edge alone is invisible and the surface does the work.
 *
 * `maxHeight` bounds a table that grows without limit (history, balances);
 * the header stays stuck to the top while its body scrolls underneath.
 */
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
