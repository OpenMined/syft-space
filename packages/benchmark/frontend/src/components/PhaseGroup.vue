<script setup lang="ts">
import { ChevronRight } from "lucide-vue-next";

// The console's outer layout: two of these ("Preparation", "Testing"), each
// collapsing a couple of phase blocks. Progressive disclosure over a flat
// list of five equal blocks — see the plan's UI section for why.
defineProps<{
  title: string;
  status: string;
  actionLabel: string;
  actionDisabled?: boolean;
  actionTitle?: string;
  open?: boolean;
}>();
const emit = defineEmits<{ action: [] }>();
</script>

<template>
  <details class="group/outer border border-border rounded-lg" :open="open ?? false">
    <summary
      class="flex items-center gap-3 p-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden"
    >
      <ChevronRight
        :size="16"
        class="transition-transform group-open/outer:rotate-90 shrink-0"
      />
      <span class="font-semibold">{{ title }}</span>
      <span class="text-sm text-muted-foreground truncate">{{ status }}</span>
      <button
        type="button"
        class="ml-auto shrink-0 rounded-md bg-primary text-primary-foreground text-sm px-3 py-1.5 disabled:opacity-50"
        :disabled="actionDisabled"
        :title="actionTitle"
        @click.stop.prevent="emit('action')"
      >
        {{ actionLabel }}
      </button>
    </summary>
    <div class="border-t border-border p-4 space-y-4">
      <slot />
    </div>
  </details>
</template>
