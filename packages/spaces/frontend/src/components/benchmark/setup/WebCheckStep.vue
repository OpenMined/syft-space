<template>
  <SetupStep
    id="bm-web"
    :step="3"
    title="Remove what the web already knows"
    description="A model with web search tries every question. Any question it can answer is removed, so what’s left can only be answered from your reporting."
  >
    <div class="flex flex-wrap gap-4">
      <div class="flex flex-[0_1_320px] flex-col gap-1">
        <Label for="bm-checker" class="text-xs font-medium text-muted-foreground">
          Web check model
        </Label>
        <ModelPicker
          :model-value="form.webCheckModel"
          trigger-id="bm-checker"
          :connection-id="connectionId"
          placeholder="Choose a model"
          @update:model-value="(v) => (form.webCheckModel = asString(v))"
        />
        <span class="text-xs text-muted-foreground">
          Answers each question using its own web search.
        </span>
      </div>
      <div class="flex flex-[0_1_300px] flex-col gap-1">
        <Label for="bm-keep" class="text-xs font-medium text-muted-foreground">
          Keep at most
        </Label>
        <span class="flex items-center gap-2">
          <NumberInput id="bm-keep" v-model="form.keepAtMost" :min="0" />
          <span class="text-sm text-muted-foreground">questions</span>
        </span>
        <span class="text-xs text-muted-foreground">
          If more survive the web check, an even mix across kinds is kept.
        </span>
      </div>
      <div class="flex flex-[0_1_320px] flex-col gap-1">
        <Label for="bm-check-judge" class="text-xs font-medium text-muted-foreground">
          Web check judge
        </Label>
        <ModelPicker
          :model-value="form.webCheckJudge"
          trigger-id="bm-check-judge"
          :connection-id="connectionId"
          :placeholder="judgeOneLabel"
          @update:model-value="(v) => (form.webCheckJudge = asString(v))"
        />
        <span class="text-xs text-muted-foreground">
          Decides whether the web answer is right.
          <button
            v-if="form.webCheckJudge"
            type="button"
            class="font-medium text-primary hover:underline"
            @click="form.webCheckJudge = ''"
          >
            Use Judge 1
          </button>
        </span>
      </div>
    </div>

    <template #advanced>
      <SettingRow
        label="When you return a question by hand"
        tip="Whether the web check may remove it again."
        for-id="bm-manual-priority"
      >
        <ChoiceSelect
          id="bm-manual-priority"
          v-model="form.manualPriority"
          :choices="MANUAL_PRIORITIES"
        />
      </SettingRow>
    </template>
  </SetupStep>
</template>

<script setup lang="ts">
/** Step 3: the web check that removes questions the web can already answer. */
import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { Label } from '@/components/ui/label'
import ChoiceSelect from './ChoiceSelect.vue'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import SetupStep from './SetupStep.vue'
import { asString } from './models'
import { MANUAL_PRIORITIES, type SetupForm } from './setupForm'

defineProps<{
  connectionId: string
  /** Placeholder of an empty judge picker: Judge 1 stands in. */
  judgeOneLabel: string
}>()

const form = defineModel<SetupForm>('form', { required: true })
</script>
