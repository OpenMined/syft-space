<script setup lang="ts">
/** An answer's web citations as links; only http(s) links are followed. */
import type { BenchmarkCitation } from '@/api/types'
import { hostOf, safeUrl } from '../filter'
import Hint from '../Hint.vue'

defineProps<{ citations: readonly BenchmarkCitation[] }>()
</script>

<template>
  <span class="flex flex-wrap gap-x-2 gap-y-0.5 text-xs">
    <Hint v-for="(cite, n) in citations" :key="`${n}-${cite.url}`" :text="cite.url">
      <a
        :href="safeUrl(cite.url)"
        target="_blank"
        rel="noopener noreferrer"
        class="max-w-60 truncate text-primary hover:underline"
        >{{ cite.title || hostOf(cite.url) }}</a
      >
    </Hint>
  </span>
</template>
