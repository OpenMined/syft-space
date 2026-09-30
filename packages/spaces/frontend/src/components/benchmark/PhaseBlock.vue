<script setup lang="ts">
/** One phase inside a PhaseGroup: its own small run button, its own status
 * line, and whatever review list or settings the caller puts in the slot. */
import { ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import InfoTip from './InfoTip.vue'

defineProps<{
  title: string
  help: string
  /** Absent where the block runs nothing of its own — it holds settings. */
  status?: string
  /**
   * 0-100 while a job with a known total is running; `'indeterminate'`
   * while one is running but has no notion of a total to divide by
   * (generation, filtering and judging never report one — only a pass
   * over arms/blocks/models does); null/absent hides the bar.
   */
  progress?: number | 'indeterminate' | null
  /** Absent where the phase has nothing to run yet — no button is drawn. */
  actionLabel?: string
  actionDisabled?: boolean
  /** Styled as a stop rather than a start — the run button turns into this
   * while this block's own job is queued or running. */
  actionDestructive?: boolean
  open?: boolean
}>()
const emit = defineEmits<{ action: []; 'update:open': [boolean] }>()
</script>

<template>
  <details
    class="group/block border border-border/60 rounded-md"
    :open="open ?? false"
    @toggle="emit('update:open', ($event.target as HTMLDetailsElement).open)"
  >
    <summary
      class="flex items-center gap-2 p-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden"
    >
      <ChevronRight class="h-3.5 w-3.5 transition-transform group-open/block:rotate-90 shrink-0" />
      <span class="font-medium text-sm text-foreground">{{ title }}</span>
      <InfoTip :text="help" />
      <span class="text-xs text-muted-foreground truncate">{{ status }}</span>
      <Button
        v-if="actionLabel"
        variant="outline"
        size="sm"
        class="ml-auto shrink-0 h-7 px-2.5 text-xs"
        :class="{ 'text-destructive hover:text-destructive': actionDestructive }"
        :disabled="actionDisabled"
        @click.stop.prevent="emit('action')"
      >
        {{ actionLabel }}
      </Button>
    </summary>
    <div v-if="progress != null" class="h-0.5 bg-muted overflow-hidden">
      <div
        v-if="progress === 'indeterminate'"
        class="h-full w-1/3 bg-primary phase-progress-indeterminate"
      />
      <div v-else class="h-full bg-primary transition-[width]" :style="{ width: `${progress}%` }" />
    </div>
    <div class="border-t border-border/60 p-3 space-y-3">
      <slot />
    </div>
  </details>
</template>

<style scoped>
.phase-progress-indeterminate {
  animation: phase-progress-slide 1.2s ease-in-out infinite;
}

@keyframes phase-progress-slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}
</style>
