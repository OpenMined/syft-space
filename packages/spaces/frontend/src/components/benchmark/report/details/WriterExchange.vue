<script setup lang="ts">
/** The source a writer call read, and the call itself with the passage marked in its prompt. */
import Exchange from './Exchange.vue'
import type { CallBlock } from './writing'

defineProps<{ block: CallBlock }>()
</script>

<template>
  <div class="space-y-2" data-testid="writer-exchange">
    <p v-if="block.fileName" class="text-xs break-all text-muted-foreground">
      {{ block.fileName }}
    </p>
    <Exchange
      v-if="block.writer"
      title="Writer"
      :model="block.writer.model"
      :system="block.writer.system"
      :prompt="block.writer.prompt"
      :highlight="block.passage"
      :reply="block.writer.reply"
      :cost-usd="block.writer.costUsd"
      :latency-s="block.writer.latencyS"
    />
    <template v-else-if="block.passage">
      <p class="text-xs text-muted-foreground">Passage</p>
      <pre
        class="max-h-80 overflow-y-auto rounded-md border border-border/60 bg-muted/50 p-2 text-xs break-words whitespace-pre-wrap"
        >{{ block.passage }}</pre
      >
    </template>
    <p v-if="block.error" class="text-xs break-words text-destructive">{{ block.error }}</p>
  </div>
</template>
