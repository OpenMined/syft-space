<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'
import type { Page } from '@/api/types'
import { Button } from '@/components/ui/button'

/** Takes the page itself so callers can't spread `items` into the DOM.
 *  Shown only when there's more than one page — a lone "1 of 1" is noise. */
const props = defineProps<{ page: Page<unknown> }>()
const emit = defineEmits<{ go: [offset: number] }>()

const limit = computed(() => props.page.limit)
const offset = computed(() => props.page.offset)
const total = computed(() => props.page.total)

const pages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)))
const current = computed(() => Math.floor(offset.value / limit.value) + 1)
const from = computed(() => offset.value + 1)
const to = computed(() => Math.min(offset.value + limit.value, total.value))
const first = computed(() => current.value === 1)
const last = computed(() => to.value >= total.value)

const steps = computed(() => [
  { icon: ChevronsLeft, label: 'First page', to: 0, disabled: first.value },
  {
    icon: ChevronLeft,
    label: 'Previous page',
    to: offset.value - limit.value,
    disabled: first.value,
  },
  {
    icon: ChevronRight,
    label: 'Next page',
    to: offset.value + limit.value,
    disabled: last.value,
  },
  {
    icon: ChevronsRight,
    label: 'Last page',
    to: (pages.value - 1) * limit.value,
    disabled: last.value,
  },
])
</script>

<template>
  <div v-if="total > limit" class="flex items-center justify-between gap-3 px-1 pt-2">
    <span class="text-xs text-muted-foreground">{{ from }}–{{ to }} of {{ total }}</span>
    <div class="flex items-center gap-2">
      <span class="text-xs text-muted-foreground">Page {{ current }} of {{ pages }}</span>
      <div class="flex items-center gap-1">
        <Button
          v-for="step in steps"
          :key="step.label"
          size="icon"
          variant="outline"
          class="h-7 w-7"
          :disabled="step.disabled"
          :title="step.label"
          @click="emit('go', Math.max(0, step.to))"
        >
          <component :is="step.icon" class="h-3.5 w-3.5" />
          <span class="sr-only">{{ step.label }}</span>
        </Button>
      </div>
    </div>
  </div>
</template>
