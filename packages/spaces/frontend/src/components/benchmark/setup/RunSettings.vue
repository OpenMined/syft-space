<template>
  <details class="group/run rounded-lg border border-border bg-card">
    <summary
      class="flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-5 py-3.5 select-none [&::-webkit-details-marker]:hidden"
    >
      <ChevronRight
        class="size-4 text-muted-foreground transition-transform group-open/run:rotate-90"
      />
      <span class="flex flex-col">
        <span class="font-semibold">Run settings</span>
        <span class="text-xs text-muted-foreground">
          Scheduled runs and retries. Rarely changed.
        </span>
      </span>
    </summary>
    <div class="flex flex-col pr-5 pb-4 pl-[46px]">
      <SettingRow
        label="Run automatically"
        help="Off means a run starts only when you press Run benchmark."
        for-id="bm-schedule"
      >
        <ChoiceSelect
          id="bm-schedule"
          v-model="form.schedule"
          :choices="SCHEDULES"
          width-class="w-44"
        />
        <Hint v-if="form.schedule === '24h'" text="Hour of the run, UTC">
          <Input
            v-model="form.scheduleAt"
            placeholder="03:00"
            class="w-22"
            aria-label="Hour of the run, UTC"
          />
        </Hint>
      </SettingRow>
      <SettingRow
        label="Stop after failures in a row"
        help="A wrong key or a server that is down won’t fix itself. 0 never stops."
        for-id="bm-failures"
      >
        <NumberInput id="bm-failures" v-model="form.maxFailures" :min="0" />
      </SettingRow>
      <SettingRow
        label="Stop at spending"
        help="0 never stops."
        tip="A run stops once its model calls cost this much."
        unit="USD"
        for-id="bm-max-usd"
      >
        <NumberInput id="bm-max-usd" v-model="form.maxJobUsd" :min="0" :step="50" />
      </SettingRow>
      <SettingRow
        label="Reuse identical answers"
        help="Turn off to measure how much answers vary."
        for-id="bm-reuse"
      >
        <Checkbox id="bm-reuse" v-model="form.reuseAnswers" />
        <span class="text-sm">On</span>
      </SettingRow>
      <SettingRow
        label="Model requests at once"
        tip="Changes how fast a run goes, not what it costs."
        for-id="bm-model-concurrency"
      >
        <NumberInput
          id="bm-model-concurrency"
          v-model="form.modelConcurrency"
          :min="1"
          :max="MODEL_CONCURRENCY_MAX"
        />
      </SettingRow>
      <div v-if="enabled" class="flex flex-wrap items-center justify-between gap-3 pt-3.5">
        <span class="text-sm text-muted-foreground">
          Stop measuring this endpoint. Settings and past runs are kept.
        </span>
        <Button
          variant="outline"
          size="sm"
          class="text-destructive hover:text-destructive"
          :disabled="saving"
          @click="emit('stopMeasuring')"
        >
          Stop measuring
        </Button>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
/** Scheduling, stop rules and speed, folded away below the five steps. */
import { ChevronRight } from 'lucide-vue-next'
import Hint from '@/components/benchmark/Hint.vue'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import ChoiceSelect from './ChoiceSelect.vue'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import { MODEL_CONCURRENCY_MAX, SCHEDULES, type SetupForm } from './setupForm'

defineProps<{
  /** Whether this endpoint is measured now. */
  enabled: boolean
  saving: boolean
}>()

const emit = defineEmits<{ stopMeasuring: [] }>()

const form = defineModel<SetupForm>('form', { required: true })
</script>
