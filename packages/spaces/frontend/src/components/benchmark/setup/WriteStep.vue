<template>
  <SetupStep
    id="bm-write"
    :step="2"
    title="Write questions"
    description="An AI model running inside your Syft Space reads every article and writes a few questions from each passage, each with one right answer taken from your reporting. A busy news day gives more questions; a quiet one gives fewer."
  >
    <div class="flex flex-wrap gap-4">
      <div class="flex flex-[0_1_320px] flex-col gap-1">
        <Label for="bm-writer" class="text-xs font-medium text-muted-foreground">
          Question writer
        </Label>
        <ModelPicker
          :model-value="form.writer"
          trigger-id="bm-writer"
          :connection-id="connectionId"
          @update:model-value="(v) => (form.writer = asString(v))"
        />
      </div>
      <div class="flex flex-[0_1_260px] flex-col gap-1">
        <Label for="bm-write-max" class="text-xs font-medium text-muted-foreground">
          Write at most
        </Label>
        <span class="flex items-center gap-2">
          <NumberInput id="bm-write-max" v-model="form.writeAtMost" :min="1" />
          <span class="text-sm text-muted-foreground">questions</span>
        </span>
        <span class="text-xs text-muted-foreground">A limit for busy news days, not a target.</span>
      </div>
    </div>

    <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
      <legend class="mb-2 p-0 text-xs font-medium text-muted-foreground">
        Kinds of question · {{ kindsOn }} of {{ kindList.length }}
      </legend>
      <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <label
          v-for="kind in kindList"
          :key="kind.key"
          class="flex cursor-pointer items-start gap-2.5 py-1.5"
        >
          <Checkbox
            class="mt-0.5"
            :model-value="!form.disabledKinds.includes(kind.key)"
            @update:model-value="(on) => setKind(kind.key, on === true)"
          />
          <span class="flex flex-col">
            <span class="text-sm font-medium">{{ kind.label }}</span>
            <span v-if="kind.help" class="text-xs text-muted-foreground">{{ kind.help }}</span>
          </span>
        </label>
      </div>
    </fieldset>

    <template #advanced>
      <SettingRow
        label="Questions per passage"
        help="Keep this low. Asking for more from one passage gives weaker questions."
        for-id="bm-ppc"
      >
        <NumberInput id="bm-ppc" v-model="form.pairsPerChunk" :min="1" />
      </SettingRow>
      <SettingRow
        label="Shortest usable passage"
        help="Shorter passages are skipped."
        unit="characters"
        for-id="bm-min-chunk"
      >
        <NumberInput id="bm-min-chunk" v-model="form.minChunkChars" :min="0" :step="50" />
      </SettingRow>
      <SettingRow
        label="Answer words found in the passage"
        help="A question is dropped if less of its answer appears in the passage."
        unit="%"
        for-id="bm-coverage"
      >
        <NumberInput id="bm-coverage" v-model="form.answerCoverage" :min="0" :max="100" :step="5" />
      </SettingRow>
      <SettingRow
        label="Question writer searches the web"
        help="Off keeps the writer to your articles."
        for-id="bm-web-writer"
      >
        <Checkbox id="bm-web-writer" v-model="form.webWriter" />
        <span class="text-sm">On</span>
      </SettingRow>
      <SettingRow
        label="Check names in questions"
        help="Drops a question whose person or company can’t be identified from the question alone."
        for-id="bm-entity-check"
      >
        <Checkbox id="bm-entity-check" v-model="form.entityCheck" />
        <span class="text-sm">On</span>
      </SettingRow>
    </template>
  </SetupStep>
</template>

<script setup lang="ts">
/** Step 2: the question writer, how many questions it writes, and of which kinds. */
import { computed } from 'vue'

import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { kindHelp, kindLabel } from '@/components/benchmark/kinds'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import SetupStep from './SetupStep.vue'
import { asString } from './models'
import { enabledKindCount, type SetupForm } from './setupForm'

const props = defineProps<{
  connectionId: string
  /** The kinds this benchmark offers, in its order. */
  kinds: string[]
}>()

const form = defineModel<SetupForm>('form', { required: true })

const kindList = computed(() =>
  props.kinds.map((key) => ({ key, label: kindLabel(key), help: kindHelp(key) })),
)

const kindsOn = computed(() => enabledKindCount(form.value, props.kinds))

function setKind(key: string, on: boolean): void {
  const off = form.value.disabledKinds.filter((item) => item !== key)
  form.value.disabledKinds = on ? off : [...off, key]
}
</script>
