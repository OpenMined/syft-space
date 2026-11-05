<script setup lang="ts">
/** One arm of a question in the details dialog: the counted verdict, the answer call, retrieval and checks. */
import { computed } from 'vue'
import Hint from '../../Hint.vue'
import CitationLinks from '../CitationLinks.vue'
import { SEARCH_UNUSED_TIP } from '../labels'
import CheckBlock from './CheckBlock.vue'
import Exchange from './Exchange.vue'
import RetrievedChunks from './RetrievedChunks.vue'
import VerdictControl from './VerdictControl.vue'
import type { ArmAudit } from './questionAudit'

const props = defineProps<{
  arm: ArmAudit
  model: string
  generator: string
  panel: string[]
  slug: string
}>()

defineEmits<{ changed: [] }>()

const callFacts = computed(() => {
  const call = props.arm.call
  if (!call) return []
  const out: string[] = []
  if (call.finish_reason) out.push(`finish: ${call.finish_reason}`)
  if (call.max_tokens) out.push(`max ${call.max_tokens} tokens`)
  if (call.length_retries)
    out.push(`${call.length_retries} ${call.length_retries === 1 ? 'retry' : 'retries'}`)
  return out
})

/** The retrieved context when the kept prompt was cut before it. */
const strayContext = computed(() => {
  const p = props.arm.answerer
  return p?.context && !p.responder_prompt.includes(p.context) ? p.context : ''
})
</script>

<template>
  <div class="space-y-4" :data-testid="`arm-${arm.arm}`">
    <VerdictControl :arm="arm" :generator="generator" :slug="slug" @changed="$emit('changed')" />

    <Exchange
      title="Answer"
      :model="model"
      :system="arm.answerer?.responder_system"
      :prompt="arm.answerer?.responder_prompt"
      :highlight="arm.answerer?.context"
      :reply="arm.answer"
      data-testid="answerer"
    >
      <template #aside>
        <span class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Hint v-if="arm.call?.truncated" text="Hit the token limit; graded on what fitted.">
            <span
              class="rounded bg-warning/20 px-1.5 py-0.5 text-foreground"
              data-testid="call-truncated"
              >cut off</span
            >
          </Hint>
          <span v-if="callFacts.length" data-testid="call-facts">{{ callFacts.join(' · ') }}</span>
        </span>
      </template>
      <p v-if="!arm.answerer" class="text-xs text-muted-foreground">Prompt not kept.</p>
      <template v-if="strayContext">
        <Hint text="The kept prompt ends before it.">
          <p class="text-xs text-muted-foreground">Retrieved context</p>
        </Hint>
        <pre
          class="max-h-80 overflow-y-auto rounded-md border border-border/60 bg-lime-200/40 p-2 text-xs break-words whitespace-pre-wrap dark:bg-lime-400/15"
          >{{ strayContext }}</pre
        >
      </template>
      <Hint v-if="arm.webSearchUnused" :text="SEARCH_UNUSED_TIP">
        <p class="text-xs text-muted-foreground" data-testid="search-unused">Searched: no</p>
      </Hint>
      <CitationLinks
        v-if="arm.citations.length"
        :citations="arm.citations"
        data-testid="citations"
      />
    </Exchange>

    <RetrievedChunks v-if="arm.retrieval" :retrieval="arm.retrieval" />

    <CheckBlock
      v-for="block in arm.blocks"
      :key="block.block"
      :block="block"
      :generator="generator"
      :panel="panel"
    />
  </div>
</template>
