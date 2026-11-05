<script setup lang="ts">
/** How one question was written and what the run's filter did to it. */
import { ref, watch } from 'vue'
import FilterPath from './FilterPath.vue'
import WriterExchange from './WriterExchange.vue'
import { loadQuestion, type QuestionOriginData } from './load'

const props = defineProps<{ slug: string; jobId: string; qaId: string }>()

const data = ref<QuestionOriginData | null>(null)
const loading = ref(false)
const failed = ref(false)
let token = 0

async function load(): Promise<void> {
  const mine = ++token
  loading.value = true
  failed.value = false
  try {
    const found = await loadQuestion(props.slug, props.jobId, props.qaId)
    if (mine === token) data.value = found
  } catch {
    if (mine === token) failed.value = true
  } finally {
    if (mine === token) loading.value = false
  }
}

watch(() => [props.slug, props.jobId, props.qaId], load, { immediate: true })
</script>

<template>
  <div class="space-y-4" data-testid="question-origin">
    <p v-if="loading && !data" class="text-sm text-muted-foreground">Loading…</p>
    <p v-else-if="failed" class="text-sm text-destructive">Could not load.</p>
    <template v-else-if="data">
      <section class="space-y-2">
        <h3 class="text-sm font-semibold">
          {{ data.block.documentTitle || data.block.fileName || 'Writer' }}
        </h3>
        <WriterExchange :block="data.block" />
      </section>
      <FilterPath :draft="data.draft" />
    </template>
  </div>
</template>
