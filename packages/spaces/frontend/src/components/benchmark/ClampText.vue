<script setup lang="ts">
/**
 * Text cut to a few lines, readable in full on hover — where it was cut.
 *
 * A question or an answer can run to a paragraph, and a page that shows every
 * one of them in full is a page nobody scrolls to the end of. Cutting them all
 * to the same height is what makes a column of answers comparable at a glance.
 *
 * The panel appears only where something was actually cut off. One that opens
 * over text the reader can already see is noise, and after a few of those
 * nobody hovers the ones that mattered.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import HoverPanel from './HoverPanel.vue'

const props = withDefaults(defineProps<{ text: string; lines?: 3 | 5 }>(), { lines: 3 })

/** Spelled out rather than built: Tailwind reads its classes out of the source. */
const CLAMP = { 3: 'line-clamp-3', 5: 'line-clamp-5' } as const

const clamp = computed(() => CLAMP[props.lines])

const body = ref<HTMLElement | null>(null)
const clipped = ref(false)

let watcher: ResizeObserver | undefined

function measure(): void {
  const element = body.value
  clipped.value = !!element && element.scrollHeight - element.clientHeight > 1
}

// Re-measured when the element is replaced — the two branches below swap one
// for the other — when it is resized, and when the text itself changes.
watch(
  body,
  (element) => {
    watcher?.disconnect()
    if (!element) return
    watcher = new ResizeObserver(measure)
    watcher.observe(element)
    measure()
  },
  { immediate: true },
)
watch(
  () => props.text,
  () => requestAnimationFrame(measure),
)
onUnmounted(() => watcher?.disconnect())
</script>

<template>
  <span class="block min-w-0">
    <HoverPanel v-if="clipped">
      <template #trigger>
        <span ref="body" class="break-words cursor-help" :class="clamp">{{ text }}</span>
      </template>
      <p class="whitespace-pre-wrap break-words">{{ text }}</p>
    </HoverPanel>
    <span v-else ref="body" class="break-words" :class="clamp">{{ text }}</span>
  </span>
</template>
