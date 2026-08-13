<script lang="ts" setup>
import type { ToasterProps } from 'vue-sonner'
import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
  XIcon,
} from 'lucide-vue-next'
import { Toaster as Sonner } from 'vue-sonner'
import { cn } from '@/lib/utils'

const props = defineProps<ToasterProps>()
</script>

<template>
  <Sonner
    :class="cn('toaster group', props.class)"
    :style="{
      '--normal-bg': 'var(--popover)',
      '--normal-text': 'var(--popover-foreground)',
      '--normal-border': 'var(--border)',
      '--border-radius': 'var(--radius)',
    }"
    v-bind="props"
  >
    <template #success-icon>
      <CircleCheckIcon class="size-4" />
    </template>
    <template #info-icon>
      <InfoIcon class="size-4" />
    </template>
    <template #warning-icon>
      <TriangleAlertIcon class="size-4" />
    </template>
    <template #error-icon>
      <OctagonXIcon class="size-4" />
    </template>
    <template #loading-icon>
      <div>
        <Loader2Icon class="size-4 animate-spin" />
      </div>
    </template>
    <template #close-icon>
      <XIcon class="size-4" />
    </template>
  </Sonner>
</template>

<!-- Global (toasts teleport to <body>, so scoped styles can't reach them):
     tuck the close button inside the toast's top-right, keep it neutral (not
     the rich-colours type tint), and reveal it only on hover of the toast. -->
<style>
[data-sonner-toast] [data-close-button] {
  left: auto;
  right: 7px;
  top: 7px;
  transform: none;
  color: var(--muted-foreground);
  background: transparent;
  border-color: transparent;
  opacity: 0;
  transition:
    opacity 0.15s ease,
    color 0.15s ease,
    background-color 0.15s ease;
}

[data-sonner-toast]:hover [data-close-button],
[data-sonner-toast]:focus-within [data-close-button] {
  opacity: 1;
}

[data-sonner-toast] [data-close-button]:hover {
  color: var(--foreground);
  background: var(--accent);
}
</style>
