<script setup lang="ts">
/** One run as a collapsible card with its figures and charts. */
import { ref, watch } from 'vue'
import { ChevronRight } from 'lucide-vue-next'

import CardCharts from './CardCharts.vue'
import CardFigures from './CardFigures.vue'
import { Button } from '@/components/ui/button'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{
  /** The card stored on the job, or the live build. */
  card: BenchmarkCard | BenchmarkReport
  /** When the run was measured, formatted. */
  measured: string
  /** Open on first draw. */
  defaultOpen?: boolean
}>()

const emit = defineEmits<{ more: [] }>()

/** Follows `defaultOpen` until the user toggles the card. */
const open = ref(props.defaultOpen ?? false)
const touched = ref(false)

watch(
  () => props.defaultOpen,
  (wanted) => {
    if (!touched.value) open.value = wanted ?? false
  },
)

function toggle(): void {
  touched.value = true
  open.value = !open.value
}
</script>

<template>
  <section class="border border-border/60 rounded-lg overflow-hidden">
    <div
      class="flex items-center gap-3 p-3 sm:p-4 cursor-pointer select-none hover:bg-muted/30"
      role="button"
      tabindex="0"
      :aria-expanded="open"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <ChevronRight
        class="h-4 w-4 text-muted-foreground shrink-0 transition-transform"
        :class="{ 'rotate-90': open }"
      />

      <div class="min-w-0">
        <div class="text-sm font-medium text-foreground truncate">
          Benchmark Result
          <span class="text-muted-foreground font-normal">{{ measured }}</span>
        </div>
      </div>
    </div>

    <div v-if="open" class="border-t border-border/60 p-3 sm:p-4 space-y-4">
      <CardFigures :card="card" />

      <CardCharts
        :answerable="card.answerable"
        :models="card.models"
        :skills="card.skills"
        :pressure="card.pressure"
        :stability="card.stability"
      />

      <div class="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" class="h-7 px-2.5 text-xs" @click="emit('more')">
          More data
          <ChevronRight class="h-3.5 w-3.5 ml-1" />
        </Button>
      </div>
    </div>
  </section>
</template>
