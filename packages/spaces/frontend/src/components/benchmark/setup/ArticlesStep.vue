<template>
  <SetupStep
    id="bm-articles"
    :step="1"
    title="Your articles"
    description="Each run uses the articles added to your Syft Space in the 24 hours before it starts."
  >
    <div
      class="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-md border border-border bg-muted/30 px-3.5 py-3 text-sm"
    >
      <div class="flex flex-wrap gap-x-6 gap-y-2">
        <span> <span class="text-muted-foreground">Data source</span> · {{ sourceLabel }} </span>
        <span v-if="articles !== null" data-testid="articles-in-window">
          <span class="text-muted-foreground">{{ windowLabel }}</span> ·
          {{ plural(articles, 'article') }}
          <Hint
            v-if="form.datasetMode === 'incremental'"
            text="Earlier runs’ questions stay in the set."
          >
            <span class="text-muted-foreground" data-testid="articles-earlier"
              >+ earlier questions</span
            >
          </Hint>
        </span>
      </div>
      <RouterLink
        v-if="dataset"
        :to="{ name: 'dataset-detail', params: { slug: dataset.name } }"
        class="font-medium text-primary hover:underline"
      >
        Manage data source
      </RouterLink>
    </div>
    <p class="text-xs text-muted-foreground">
      Connect a source such as WordPress to add new articles automatically, or upload files by hand.
    </p>

    <template #advanced>
      <SettingRow
        label="Time window"
        help="1 means articles added in the last 24 hours."
        unit="days"
        for-id="bm-window"
      >
        <NumberInput id="bm-window" v-model="form.windowDays" :min="0" />
      </SettingRow>
      <SettingRow
        label="How the question set changes"
        help="Rolling is right for news: each run uses only the newest articles."
        for-id="bm-mode"
      >
        <ChoiceSelect id="bm-mode" v-model="form.datasetMode" :choices="DATASET_MODES" />
      </SettingRow>
      <SettingRow
        label="Write new questions before each run"
        help="Turn off only if questions are added another way."
        for-id="bm-cycle"
      >
        <Checkbox id="bm-cycle" v-model="form.generateInCycle" />
        <span class="text-sm">On</span>
      </SettingRow>
      <SettingRow
        label="Index collection"
        help="Worked out from your data. Fill in only if that turns out wrong."
        for-id="bm-collection"
      >
        <Input
          id="bm-collection"
          v-model="form.collection"
          :placeholder="resolvedCollection || 'Automatic'"
          class="w-70"
        />
      </SettingRow>
    </template>
  </SetupStep>
</template>

<script setup lang="ts">
/** Step 1: the data source and the window of articles a run uses. */
import { computed } from 'vue'
import Hint from '@/components/benchmark/Hint.vue'

import { plural } from '@/components/benchmark/labels'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { SOURCE_PRESENTATION } from '@/config/sources'
import ChoiceSelect from './ChoiceSelect.vue'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import SetupStep from './SetupStep.vue'
import { DATASET_MODES, type SetupForm } from './setupForm'

const props = defineProps<{
  dataset: { name: string; dtype: string } | null
  /** Articles in the window; null while unknown. */
  articles: number | null
  /** The collection the benchmark works out when none is set. */
  resolvedCollection: string
}>()

const form = defineModel<SetupForm>('form', { required: true })

const sourceLabel = computed(() => {
  const dtype = props.dataset?.dtype
  if (!dtype) return 'None'
  return SOURCE_PRESENTATION[dtype]?.label ?? dtype
})

const windowLabel = computed(() => {
  const days = Number(form.value.windowDays) || 0
  if (days <= 0) return 'Added so far'
  return days === 1 ? 'Added in the last 24 hours' : `Added in the last ${days} days`
})
</script>
