<script setup lang="ts">
/** One model call: who was asked, the system prompt, the prompt and the reply. */
import { computed } from 'vue'
import { modelName } from '../labels'

const props = defineProps<{
  title: string
  model?: string | null
  system?: string | null
  prompt?: string | null
  /** Part of the prompt to highlight, e.g. the retrieved context. */
  highlight?: string | null
  reply?: string | null
  costUsd?: number | null
  latencyS?: number | null
}>()

const parts = computed(() => {
  const text = props.prompt ?? ''
  const mark = props.highlight ?? ''
  const at = mark ? text.indexOf(mark) : -1
  if (at < 0) return [{ text, marked: false }]
  return [
    { text: text.slice(0, at), marked: false },
    { text: mark, marked: true },
    { text: text.slice(at + mark.length), marked: false },
  ].filter((part) => part.text)
})

const facts = computed(() => {
  const out: string[] = []
  if (props.model) out.push(modelName(props.model))
  if (typeof props.latencyS === 'number') out.push(`${props.latencyS.toFixed(1)} s`)
  if (typeof props.costUsd === 'number') out.push(`$${props.costUsd.toFixed(4)}`)
  return out.join(' · ')
})

const PRE =
  'mt-1 max-h-80 overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-border/60 p-2 text-xs text-foreground'
</script>

<template>
  <section class="space-y-1.5" data-testid="exchange">
    <div class="flex flex-wrap items-baseline gap-x-2">
      <h4 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {{ title }}
      </h4>
      <span v-if="facts" class="text-xs text-muted-foreground">{{ facts }}</span>
      <span class="ml-auto"><slot name="aside" /></span>
    </div>
    <details v-if="system">
      <summary class="cursor-pointer text-xs text-muted-foreground">System prompt</summary>
      <pre :class="PRE" class="bg-muted/50">{{ system }}</pre>
    </details>
    <template v-if="prompt">
      <p class="text-xs text-muted-foreground">Prompt</p>
      <pre :class="PRE" class="bg-muted/50"><span
          v-for="(part, n) in parts"
          :key="n"
          :class="part.marked && 'rounded bg-lime-200/70 dark:bg-lime-400/25'"
        >{{ part.text }}</span></pre>
    </template>
    <template v-if="reply">
      <p class="text-xs text-muted-foreground">Reply</p>
      <pre :class="PRE" class="bg-card">{{ reply }}</pre>
    </template>
    <slot />
  </section>
</template>
