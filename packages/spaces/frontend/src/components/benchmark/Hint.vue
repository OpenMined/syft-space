<script setup lang="ts">
/**
 * The wrapped element with a short explanation on hover, keyboard focus or tap; the element alone
 * without one. The element is made focusable unless `focusable` is false: for an element that holds
 * its own controls or sits inside one, where an extra focus stop would nest.
 */
import { ref, type Component, type FunctionalComponent } from 'vue'
import { injectTooltipProviderContext } from 'reka-ui'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

withDefaults(defineProps<{ text?: string | null; focusable?: boolean }>(), {
  text: null,
  focusable: true,
})

const Passthrough: FunctionalComponent = (_, { slots }) => slots.default?.()
/** App.vue provides one TooltipProvider, so tooltips share the skip delay; a Hint mounted outside it brings its own. */
const Provider: Component = injectTooltipProviderContext(null) ? Passthrough : TooltipProvider

const CONTROLS = 'a[href], button, input, select, textarea, summary, [role="button"]'

const open = ref(false)
let tap: { wasOpen: boolean } | null = null

/** Touch has no hover: a tap on the element toggles the tooltip; a tap on a control is left to it. */
function onPointerdown(event: PointerEvent): void {
  const control = (event.target as Element | null)?.closest(CONTROLS)
  tap =
    event.pointerType === 'touch' && (!control || control === event.currentTarget)
      ? { wasOpen: open.value }
      : null
}

function onClick(): void {
  if (!tap) return
  const next = !tap.wasOpen
  tap = null
  // Runs after the trigger's own click handling, which closes the tooltip.
  queueMicrotask(() => (open.value = next))
}
</script>

<template>
  <Provider v-if="text">
    <Tooltip v-model:open="open" ignore-non-keyboard-focus>
      <TooltipTrigger
        as-child
        :tabindex="focusable ? 0 : undefined"
        @pointerdown.capture="onPointerdown"
        @click="onClick"
      >
        <slot />
      </TooltipTrigger>
      <TooltipContent class="max-w-64 whitespace-pre-line" data-testid="hint">{{
        text
      }}</TooltipContent>
    </Tooltip>
  </Provider>
  <slot v-else />
</template>
