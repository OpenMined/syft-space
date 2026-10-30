<script setup lang="ts">
import { computed, ref } from 'vue'
import { UserRound } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkVerdict } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiErrorDetail } from '@/lib/errors'
import { outcomeLabel } from '../labels'
import Hint from '../../Hint.vue'
import VerdictPill from './VerdictPill.vue'
import type { ArmAudit } from './questionAudit'

const props = defineProps<{
  arm: ArmAudit
  generator: string
  slug: string
}>()

const emit = defineEmits<{ changed: [] }>()

/** The kind graded on key facts, the only one with an incomplete verdict. */
const KEY_FACTS_KIND = 'tiered_explanation'

const choices = computed<BenchmarkVerdict[]>(() => [
  'correct',
  'abstain',
  'hallucinate',
  ...(props.generator === KEY_FACTS_KIND ? (['incomplete'] as const) : []),
  ...(props.arm.citations.length ? (['web_sourced'] as const) : []),
])

const editing = ref(false)
const choice = ref<BenchmarkVerdict | null>(null)
const reason = ref('')
const busy = ref(false)

function start(): void {
  choice.value = null
  reason.value = ''
  editing.value = true
}

async function act(call: () => Promise<unknown>, failed: string): Promise<void> {
  busy.value = true
  try {
    await call()
    editing.value = false
    emit('changed')
  } catch (e) {
    toast.error(apiErrorDetail(e, failed))
  } finally {
    busy.value = false
  }
}

function save(): Promise<void> {
  const id = props.arm.actionId
  const verdict = choice.value
  if (!id || !verdict) return Promise.resolve()
  return act(
    () => benchmarksApi.overrideVerdict(props.slug, id, verdict, reason.value.trim()),
    'Could not change this verdict',
  )
}

function undo(): Promise<void> {
  const id = props.arm.override?.id
  if (!id) return Promise.resolve()
  return act(() => benchmarksApi.withdrawVerdict(props.slug, id), 'Could not undo this verdict')
}
</script>

<template>
  <div class="space-y-2" data-testid="verdict-control">
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <Hint text="The primary judge's verdict on the direct check; the owner's wins.">
        <span class="text-muted-foreground">Counted</span>
      </Hint>
      <VerdictPill
        v-if="arm.counted"
        :verdict="arm.counted.verdict"
        :generator="generator"
        :behavior="arm.override ? null : arm.counted.behavior"
        data-testid="counted-verdict"
      />
      <span
        v-if="arm.override"
        class="flex items-center gap-1 text-xs text-muted-foreground"
        data-testid="owner-verdict"
        ><UserRound class="size-3.5" aria-hidden="true" />owner</span
      >
      <span class="ml-auto flex gap-1.5">
        <Button
          v-if="arm.override"
          variant="outline"
          size="sm"
          :disabled="busy"
          data-testid="undo-verdict"
          @click="undo"
          >Undo</Button
        >
        <Button
          v-if="arm.actionId && !editing"
          variant="outline"
          size="sm"
          :disabled="busy"
          data-testid="change-verdict"
          @click="start"
          >Change verdict</Button
        >
      </span>
    </div>
    <p v-if="arm.override?.reasoning" class="text-xs text-muted-foreground">
      {{ arm.override.reasoning }}
    </p>

    <form
      v-if="editing"
      class="flex flex-wrap items-center gap-2 rounded-md border border-border p-2"
      data-testid="verdict-form"
      @submit.prevent="save"
    >
      <span class="flex flex-wrap gap-1" role="group" aria-label="Verdict">
        <Button
          v-for="v in choices"
          :key="v"
          type="button"
          size="sm"
          :variant="choice === v ? 'default' : 'outline'"
          :aria-pressed="choice === v"
          :data-testid="`choice-${v}`"
          @click="choice = v"
          >{{ outcomeLabel(generator, v) }}</Button
        >
      </span>
      <Input
        v-model="reason"
        class="h-8 min-w-48 flex-1"
        placeholder="Why"
        aria-label="Why"
        data-testid="verdict-reason"
      />
      <Button type="submit" size="sm" :disabled="busy || !choice" data-testid="save-verdict"
        >Save</Button
      >
      <Button type="button" variant="ghost" size="sm" :disabled="busy" @click="editing = false"
        >Cancel</Button
      >
    </form>
  </div>
</template>
