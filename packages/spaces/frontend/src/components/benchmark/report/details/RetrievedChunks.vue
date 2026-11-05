<script setup lang="ts">
import { reactive } from 'vue'
import Hint from '../../Hint.vue'
import { inPrompt, shortened, sourceText, type Retrieval } from './questionAudit'

defineProps<{ retrieval: Retrieval }>()

const open = reactive(new Set<number>())

function toggle(index: number): void {
  if (!open.delete(index)) open.add(index)
}
</script>

<template>
  <section class="space-y-1.5" data-testid="retrieved">
    <div class="flex flex-wrap items-baseline gap-x-2">
      <h4 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Retrieved</h4>
      <Hint text="Where the passage the question was written from ranked.">
        <span
          class="text-xs"
          :class="retrieval.hit ? 'text-muted-foreground' : 'text-amber-700 dark:text-amber-400'"
          data-testid="retrieved-source"
          >{{ sourceText(retrieval) }}</span
        >
      </Hint>
    </div>
    <p v-if="!retrieval.fragments" class="text-xs text-muted-foreground">Not kept.</p>
    <ol v-else class="space-y-1">
      <li
        v-for="(fragment, i) in retrieval.fragments"
        :key="i"
        class="rounded-md border border-border/60 p-2 text-xs"
        :class="inPrompt(retrieval, i) === false && 'opacity-55'"
        data-testid="chunk"
      >
        <p class="flex flex-wrap items-center gap-2">
          <b class="font-semibold">{{ i + 1 }}</b>
          <span class="min-w-0 truncate text-muted-foreground">{{
            fragment.file_name || 'unnamed'
          }}</span>
          <span
            v-if="retrieval.hit && retrieval.rank === i + 1"
            class="rounded bg-lime-200/70 px-1.5 text-lime-950 dark:bg-lime-400/25 dark:text-lime-200"
            data-testid="chunk-source"
            >source</span
          >
          <Hint
            v-if="inPrompt(retrieval, i) === false"
            :text="`Past the first ${retrieval.contextDocs}: not in the prompt.`"
          >
            <span class="text-muted-foreground">not in prompt</span>
          </Hint>
          <Hint
            v-if="shortened(fragment)"
            :text="`${fragment.chars} characters, cut to ${fragment.content.length}.`"
          >
            <span class="text-muted-foreground">cut</span>
          </Hint>
          <Hint text="Similarity to the question.">
            <span class="ml-auto shrink-0 text-muted-foreground tabular-nums">{{
              fragment.score.toFixed(3)
            }}</span>
          </Hint>
        </p>
        <button
          type="button"
          class="mt-1 block w-full cursor-pointer text-left break-words whitespace-pre-wrap text-foreground/80"
          :class="!open.has(i) && 'line-clamp-3'"
          :aria-expanded="open.has(i)"
          @click="toggle(i)"
          v-text="fragment.content"
        />
      </li>
    </ol>
  </section>
</template>
