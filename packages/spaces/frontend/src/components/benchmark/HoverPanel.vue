<script setup lang="ts">
/** A hover card for long content; unlike a tooltip, it stays open while the pointer is inside. */
import { HoverCardContent, HoverCardPortal, HoverCardRoot, HoverCardTrigger } from 'reka-ui'

withDefaults(defineProps<{ width?: string }>(), { width: 'w-96' })
</script>

<template>
  <HoverCardRoot :open-delay="150" :close-delay="120">
    <HoverCardTrigger as-child>
      <slot name="trigger" />
    </HoverCardTrigger>
    <HoverCardPortal>
      <HoverCardContent
        side="top"
        align="start"
        :side-offset="6"
        :collision-padding="12"
        class="z-50 max-h-72 overflow-y-auto rounded-md border border-border bg-popover p-3 text-xs text-popover-foreground shadow-md"
        :class="width"
      >
        <slot />
      </HoverCardContent>
    </HoverCardPortal>
  </HoverCardRoot>
</template>
