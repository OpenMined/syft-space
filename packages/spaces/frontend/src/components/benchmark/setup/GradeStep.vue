<template>
  <SetupStep
    id="bm-grade"
    :step="5"
    title="Grade the answers"
    description="AI judges grade every answer as right, didn’t know or hallucinated. Judge 1’s verdict is the one that counts; the others are a second opinion."
  >
    <div class="flex max-w-[680px] flex-col gap-1.5">
      <div
        v-for="slot in judgeSlots"
        :key="slot.index"
        class="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-1"
        :data-testid="`judge-${slot.index + 1}`"
      >
        <Label
          :for="`bm-judge-${slot.index + 1}`"
          class="flex flex-[0_0_120px] flex-col items-start gap-0"
        >
          <span class="font-medium">Judge {{ slot.index + 1 }}</span>
          <span class="text-xs font-normal text-muted-foreground">
            {{ slot.index === 0 ? 'Main judge' : 'Second opinion' }}
          </span>
        </Label>
        <div class="min-w-0 flex-[1_1_220px]">
          <ModelPicker
            :model-value="slot.id"
            :trigger-id="`bm-judge-${slot.index + 1}`"
            :connection-id="connectionId"
            :exclude="slot.exclude"
            :warn="slot.clashWith.length > 0"
            :described-by="slot.clashWith.length ? `bm-judge-note-${slot.index + 1}` : ''"
            placeholder="Choose a judge"
            @update:model-value="(v) => setJudge(slot.index, asString(v))"
          />
        </div>
        <span
          v-if="slot.clashWith.length"
          :id="`bm-judge-note-${slot.index + 1}`"
          class="inline-flex items-center gap-1.5 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
        >
          <TriangleAlert class="size-3.5" />
          Same company as {{ slot.clashWith.join(', ') }}
        </span>
      </div>
    </div>
    <p class="text-xs text-muted-foreground">
      How often the second opinions agree with Judge 1 is shown with the results, as a check on the
      grading.
    </p>

    <template #advanced>
      <SettingRow
        label="Number of judges"
        help="With one judge there’s no second opinion, so agreement can’t be checked."
        for-id="bm-judge-count"
      >
        <ChoiceSelect
          id="bm-judge-count"
          :model-value="String(form.judgeCount)"
          :choices="JUDGE_COUNTS"
          @update:model-value="(v) => (form.judgeCount = Number(v))"
        />
      </SettingRow>
      <SettingRow
        label="Same-company rule"
        help="What happens when a judge and a model being tested are from the same company. You’re asked before the run starts either way."
        for-id="bm-policy"
      >
        <ChoiceSelect id="bm-policy" v-model="form.judgePolicy" :choices="JUDGE_POLICIES" />
      </SettingRow>
      <SettingRow
        label="Facts an explanation must cover"
        help="For “Explaining a story simply”. A plain answer can drop details."
        unit="%"
        for-id="bm-key-facts"
      >
        <NumberInput id="bm-key-facts" v-model="form.keyFacts" :min="0" :max="100" :step="5" />
      </SettingRow>
      <SettingRow
        label="Text similarity scores"
        help="Shown to researchers only, never in results."
      >
        <span class="flex flex-wrap gap-x-4 gap-y-1.5">
          <label
            v-for="metric in TEXT_METRICS"
            :key="metric.value"
            class="flex cursor-pointer items-center gap-1.5 text-sm"
          >
            <Checkbox
              :model-value="form.textMetrics.includes(metric.value)"
              @update:model-value="(on) => setMetric(metric.value, on === true)"
            />
            {{ metric.label }}
          </label>
        </span>
      </SettingRow>
      <SettingRow
        label="Judges search the web"
        help="Off keeps judges to the question and the expected answer."
        for-id="bm-web-judges"
      >
        <Checkbox id="bm-web-judges" v-model="form.webJudges" />
        <span class="text-sm">On</span>
      </SettingRow>
      <SettingRow
        label="Judge temperature"
        tip="Empty uses the model’s default."
        for-id="bm-judge-temp"
      >
        <NumberInput
          id="bm-judge-temp"
          v-model="form.judgeTemperature"
          :min="0"
          :max="2"
          :step="0.1"
        />
      </SettingRow>
      <SettingRow
        label="Judge reasoning"
        tip="Less reasoning grades faster."
        for-id="bm-judge-reasoning"
      >
        <ChoiceSelect
          id="bm-judge-reasoning"
          v-model="form.judgeReasoning"
          :choices="JUDGE_REASONING"
        />
      </SettingRow>
    </template>
  </SetupStep>
</template>

<script setup lang="ts">
/** Step 5: the judges and how they grade. */
import { TriangleAlert } from 'lucide-vue-next'

import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import ChoiceSelect from './ChoiceSelect.vue'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import SetupStep from './SetupStep.vue'
import { asString } from './models'
import {
  JUDGE_POLICIES,
  JUDGE_REASONING,
  TEXT_METRICS,
  type Choice,
  type JudgeSlot,
  type SetupForm,
} from './setupForm'

defineProps<{ connectionId: string; judgeSlots: JudgeSlot[] }>()

const form = defineModel<SetupForm>('form', { required: true })

const JUDGE_COUNTS: Choice[] = [
  { value: '1', label: '1 judge' },
  { value: '2', label: '2 judges' },
  { value: '3', label: '3 judges' },
]

function setJudge(slot: number, id: string): void {
  const next = [...form.value.judges]
  next[slot] = id
  form.value.judges = next
}

function setMetric(metric: string, on: boolean): void {
  const rest = form.value.textMetrics.filter((item) => item !== metric)
  form.value.textMetrics = on ? [...rest, metric] : rest
}
</script>
