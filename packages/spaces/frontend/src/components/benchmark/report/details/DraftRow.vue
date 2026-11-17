<script setup lang="ts">
/** One question: what became of it, and on demand its filter path and the owner's controls. */
import { ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import type { BenchmarkPair, BenchmarkPairStatus } from '@/api/types'
import FilterPath from './FilterPath.vue'
import { fateLabel, fateTone, type DraftView } from './writing'

defineProps<{ draft: DraftView; busy: boolean }>()
const emit = defineEmits<{ setStatus: [BenchmarkPair, BenchmarkPairStatus] }>()

const open = ref(false)
</script>

<template>
  <li class="rounded-md border border-border/60 text-sm" data-testid="draft-row">
    <button
      type="button"
      class="flex w-full items-start gap-2 p-2 text-left"
      :aria-expanded="open"
      data-testid="draft-toggle"
      @click="open = !open"
    >
      <ChevronRight
        class="mt-0.5 h-3.5 w-3.5 shrink-0 transition-transform"
        :class="{ 'rotate-90': open }"
      />
      <span class="line-clamp-2 min-w-0 flex-1 break-words">{{ draft.question }}</span>
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-xs"
        :class="fateTone(draft.fate)"
        data-testid="draft-fate"
        >{{ fateLabel(draft.fate) }}</span
      >
    </button>
    <div v-if="open" class="space-y-3 border-t border-border/60 p-2.5 pl-7.5">
      <p class="text-xs break-words whitespace-pre-line text-muted-foreground">
        {{ draft.answer }}
      </p>
      <FilterPath :draft="draft" />
      <div v-if="draft.pair" class="flex justify-end gap-2">
        <Button
          v-if="draft.status !== 'active'"
          variant="outline"
          size="sm"
          class="h-7 px-2 text-xs"
          :disabled="busy"
          @click="emit('setStatus', draft.pair, 'active')"
        >
          Mark active
        </Button>
        <Button
          v-if="draft.status !== 'rejected'"
          variant="outline"
          size="sm"
          class="h-7 px-2 text-xs"
          :disabled="busy"
          @click="emit('setStatus', draft.pair, 'rejected')"
        >
          Reject
        </Button>
      </div>
    </div>
  </li>
</template>
