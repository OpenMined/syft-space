<script setup lang="ts">
/** One graded (or still-pending) answer — extracted from ResultList, which groups these. */
import { Button } from '@/components/ui/button'
import type { BenchmarkResult, BenchmarkVerdict } from '@/api/types'

defineProps<{ result: BenchmarkResult; busy: boolean }>()
const emit = defineEmits<{ override: [verdict: BenchmarkVerdict] }>()
</script>

<template>
  <li
    class="rounded-md border border-border/60 p-2.5 text-sm space-y-1"
    :class="{ 'opacity-50': !result.is_latest }"
  >
    <div class="flex items-start gap-2">
      <div class="flex-1 min-w-0">
        <p class="font-medium break-words text-foreground">{{ result.question }}</p>
        <p class="text-muted-foreground break-words">{{ result.answer }}</p>
      </div>
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-xs"
        :class="{
          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400': result.verdict === 'correct',
          'bg-destructive/10 text-destructive': result.verdict === 'hallucinate',
          'bg-muted text-muted-foreground':
            result.verdict === 'abstain' || result.verdict === 'pending',
        }"
      >
        {{ result.verdict }}
      </span>
    </div>
    <p v-if="result.reasoning" class="text-xs text-muted-foreground italic">
      {{ result.reasoning }}
    </p>
    <div class="flex items-center gap-2 pt-1">
      <span class="text-xs text-muted-foreground">{{ result.model }}</span>
      <span v-if="!result.is_latest" class="text-xs text-muted-foreground">superseded</span>
      <template v-if="result.is_latest">
        <Button
          v-if="result.verdict !== 'correct'"
          variant="outline"
          size="sm"
          class="ml-auto h-7 px-2 text-xs"
          :disabled="busy"
          @click="emit('override', 'correct')"
        >
          Mark correct
        </Button>
        <Button
          v-if="result.verdict !== 'hallucinate'"
          variant="outline"
          size="sm"
          class="h-7 px-2 text-xs"
          :class="{ 'ml-auto': result.verdict === 'correct' }"
          :disabled="busy"
          @click="emit('override', 'hallucinate')"
        >
          Mark hallucination
        </Button>
      </template>
    </div>
  </li>
</template>
