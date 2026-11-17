<script setup lang="ts">
/** One writer call, collapsed to its source: the call, every draft it kept and every one it dropped. */
import { computed, ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import type { BenchmarkPair, BenchmarkPairStatus } from '@/api/types'
import DraftRow from './DraftRow.vue'
import WriterExchange from './WriterExchange.vue'
import type { CallBlock } from './writing'

const props = defineProps<{ block: CallBlock; busyId: string | null }>()
const emit = defineEmits<{ setStatus: [BenchmarkPair, BenchmarkPairStatus] }>()

const open = ref(false)

const countText = computed(() => {
  const parts: string[] = []
  if (props.block.drafts.length) parts.push(`${props.block.drafts.length} written`)
  if (props.block.dropped.length) parts.push(`${props.block.dropped.length} dropped`)
  if (props.block.error) parts.push('failed')
  return parts.join(' · ')
})
</script>

<template>
  <section class="rounded-md border border-border" data-testid="call-block">
    <button
      type="button"
      class="flex w-full items-center gap-2 p-2.5 text-left"
      :aria-expanded="open"
      data-testid="call-toggle"
      @click="open = !open"
    >
      <ChevronRight
        class="h-3.5 w-3.5 shrink-0 transition-transform"
        :class="{ 'rotate-90': open }"
      />
      <span class="min-w-0 flex-1 truncate text-sm font-medium">
        {{ block.documentTitle || block.fileName || 'Unknown source' }}
      </span>
      <span class="shrink-0 text-xs text-muted-foreground">{{ countText }}</span>
    </button>
    <div v-if="open" class="space-y-3 border-t border-border p-2.5">
      <WriterExchange :block="block" />
      <ul v-if="block.drafts.length" class="space-y-1.5">
        <DraftRow
          v-for="draft in block.drafts"
          :key="draft.id"
          :draft="draft"
          :busy="busyId === draft.id"
          @set-status="(pair, status) => emit('setStatus', pair, status)"
        />
      </ul>
      <div v-if="block.dropped.length" class="space-y-1.5" data-testid="dropped-drafts">
        <h4 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          Dropped while writing
        </h4>
        <ul class="space-y-1.5">
          <li
            v-for="(d, n) in block.dropped"
            :key="n"
            class="space-y-0.5 rounded-md border border-dashed border-border p-2 text-sm"
          >
            <p class="break-words">{{ d.question }}</p>
            <p class="text-xs break-words text-muted-foreground">{{ d.answer }}</p>
            <p class="text-xs text-destructive">{{ d.reason }}</p>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
