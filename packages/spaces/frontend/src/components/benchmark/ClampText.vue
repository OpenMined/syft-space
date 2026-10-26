<script setup lang="ts">
/** Text clamped to a few lines; the full text shows on hover only when it is cut. */
import { computed, onUnmounted, ref, watch } from 'vue'
import HoverPanel from './HoverPanel.vue'

const props = withDefaults(defineProps<{ text: string; lines?: 3 | 5 }>(), { lines: 3 })

/** Literal class names so Tailwind finds them. */
const CLAMP = { 3: 'line-clamp-3', 5: 'line-clamp-5' } as const

const clamp = computed(() => CLAMP[props.lines])

const body = ref<HTMLElement | null>(null)
const clipped = ref(false)

let watcher: ResizeObserver | undefined

function measure(): void {
  const element = body.value
  clipped.value = !!element && element.scrollHeight - element.clientHeight > 1
}

// Re-measure when the element is swapped or resized and when the text changes.
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
