<script setup lang="ts">
/** One pair's question, answer, status and the actions available on it. */
import { Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import type { BenchmarkPair, BenchmarkPairStatus } from '@/api/types'

defineProps<{ pair: BenchmarkPair; busy: boolean }>()
const emit = defineEmits<{
  setStatus: [BenchmarkPairStatus]
  remove: []
}>()
</script>

<template>
  <li class="rounded-md border border-border/60 p-2.5 text-sm space-y-1">
    <div class="flex items-start gap-2">
      <div class="flex-1 min-w-0">
        <p class="font-medium break-words text-foreground">{{ pair.question }}</p>
        <p class="text-muted-foreground break-words">{{ pair.answer }}</p>
      </div>
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-xs"
        :class="{
          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400': pair.status === 'active',
          'bg-destructive/10 text-destructive': pair.status === 'rejected',
          'bg-muted text-muted-foreground': pair.status === 'pending' || pair.status === 'retired',
        }"
      >
        {{ pair.status }}
      </span>
    </div>
    <p v-if="pair.status_note" class="text-xs text-muted-foreground italic">
      {{ pair.status_note }}
    </p>
    <div class="flex items-center gap-2 pt-1">
      <Button
        v-if="pair.status !== 'active'"
        variant="outline"
        size="sm"
        class="ml-auto h-7 px-2 text-xs"
        :disabled="busy"
        @click="emit('setStatus', 'active')"
      >
        Mark active
      </Button>
      <Button
        v-if="pair.status !== 'rejected'"
        variant="outline"
        size="sm"
        class="h-7 px-2 text-xs"
        :disabled="busy"
        @click="emit('setStatus', 'rejected')"
      >
        Reject
      </Button>
      <Button
        variant="outline"
        size="sm"
        class="h-7 px-1.5 text-destructive hover:text-destructive disabled:opacity-30"
        :disabled="busy || pair.has_results"
        :title="pair.has_results ? 'Has results — change its status instead of deleting' : 'Delete for good'"
        @click="emit('remove')"
      >
        <Trash2 class="h-3.5 w-3.5" />
      </Button>
    </div>
  </li>
</template>
