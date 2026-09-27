<script setup lang="ts">
import { ChevronRight } from "lucide-vue-next";
import InfoTip from "./InfoTip.vue";

// One phase inside a PhaseGroup: its own small run button, its own status
// line, and whatever review list the caller puts in the slot.
defineProps<{
  title: string;
  help: string;
  status: string;
  /**
   * 0-100 while a job with a known total is running; `'indeterminate'`
   * while one is running but has no notion of a total to divide by
   * (generation, filtering and judging never report one — only a pass
   * over arms/blocks/models does); null/absent hides the bar.
   */
  progress?: number | "indeterminate" | null;
  actionLabel: string;
  actionDisabled?: boolean;
  open?: boolean;
}>();
const emit = defineEmits<{ action: [] }>();
</script>

<template>
  <details
    class="group/block border border-border/60 rounded-md"
    :open="open ?? false"
  >
    <summary
      class="flex items-center gap-2 p-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden"
    >
      <ChevronRight
        :size="14"
        class="transition-transform group-open/block:rotate-90 shrink-0"
      />
      <span class="font-medium text-sm">{{ title }}</span>
      <InfoTip :text="help" />
      <span class="text-xs text-muted-foreground truncate">{{ status }}</span>
      <button
        type="button"
        class="ml-auto shrink-0 rounded-md border border-border text-sm px-2.5 py-1 hover:bg-accent disabled:opacity-50"
        :disabled="actionDisabled"
        @click.stop.prevent="emit('action')"
      >
        {{ actionLabel }}
      </button>
    </summary>
    <div v-if="progress != null" class="h-0.5 bg-muted overflow-hidden">
      <div
        v-if="progress === 'indeterminate'"
        class="h-full w-1/3 bg-primary phase-progress-indeterminate"
      />
      <div
        v-else
        class="h-full bg-primary transition-[width]"
        :style="{ width: `${progress}%` }"
      />
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
