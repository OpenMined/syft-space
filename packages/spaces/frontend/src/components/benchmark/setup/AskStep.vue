<template>
  <SetupStep
    id="bm-ask"
    :step="4"
    title="Ask the models"
    description="Each model answers every question twice: on its own, and with excerpts from your archive. The difference is what your data adds."
  >
    <div class="flex flex-col gap-1.5">
      <Label for="bm-models" class="text-xs font-medium text-muted-foreground">
        Models to test
      </Label>
      <ModelPicker
        :model-value="form.models"
        multiple
        trigger-id="bm-models"
        add-label="Add a model…"
        placeholder="Add a model…"
        :connection-id="connectionId"
        @update:model-value="(v) => (form.models = asList(v))"
      />
      <Hint v-for="(name, at) in skippedNames" :key="at" text="Takes no temperature setting.">
        <span class="text-xs text-amber-800 dark:text-amber-300" data-testid="no-temperature-note">
          {{ name }} · Monte Carlo skipped
        </span>
      </Hint>
    </div>
    <fieldset class="m-0 flex flex-col gap-1.5 border-0 p-0">
      <legend class="mb-1.5 p-0 text-xs font-medium text-muted-foreground">Search the web</legend>
      <label class="flex cursor-pointer items-start gap-2.5">
        <Checkbox v-model="form.webAlone" class="mt-0.5" />
        <span class="flex flex-col">
          <span class="text-sm font-medium">On its own</span>
          <span class="text-xs text-muted-foreground">
            The model may search the web when it answers without your data.
          </span>
        </span>
      </label>
      <span v-if="form.webAlone" class="flex items-center gap-2 pl-6.5">
        <Label for="bm-web-searches" class="text-xs font-normal text-muted-foreground">
          Searches per answer, at most
        </Label>
        <Hint text="0 means the provider’s own limit (30).">
          <NumberInput
            id="bm-web-searches"
            v-model="form.webMaxSearches"
            :min="0"
            :max="WEB_SEARCHES_MAX"
          />
        </Hint>
      </span>
      <label class="flex cursor-pointer items-start gap-2.5">
        <Checkbox v-model="form.webWithData" class="mt-0.5" />
        <span class="flex flex-col">
          <span class="text-sm font-medium">With your data</span>
          <span class="text-xs text-muted-foreground">
            The model may also search the web when it has your excerpts.
          </span>
        </span>
      </label>
    </fieldset>
    <fieldset class="m-0 flex flex-col gap-1.5 border-0 p-0">
      <legend class="mb-1.5 p-0 text-xs font-medium text-muted-foreground">
        Reliability checks
      </legend>
      <label class="flex cursor-pointer items-start gap-2.5">
        <Checkbox v-model="form.challenge" class="mt-0.5" />
        <span class="flex flex-col">
          <span class="text-sm font-medium">Challenge right answers</span>
          <span class="text-xs text-muted-foreground">
            Reply “Are you sure?” and see whether the model holds its answer.
          </span>
        </span>
      </label>
      <label class="flex cursor-pointer items-start gap-2.5">
        <Checkbox v-model="form.repeat" class="mt-0.5" />
        <span class="flex flex-col">
          <span class="text-sm font-medium">Ask each question again</span>
          <span class="text-xs text-muted-foreground">
            Repeat each question to see whether the model gives the same answer.
          </span>
        </span>
      </label>
    </fieldset>

    <template #advanced>
      <SettingRow
        label="Excerpts the search returns"
        help="How many passages your archive search finds for each question."
        for-id="bm-topk"
      >
        <NumberInput id="bm-topk" v-model="form.retrievalTopK" :min="1" :max="50" />
      </SettingRow>
      <SettingRow
        label="Excerpts sent with each question"
        help="How many of those go to the model with the question."
        for-id="bm-ctx-docs"
      >
        <NumberInput id="bm-ctx-docs" v-model="form.contextDocs" :min="1" :max="20" />
      </SettingRow>
      <SettingRow label="Longest excerpt" unit="characters" for-id="bm-fragment">
        <NumberInput
          id="bm-fragment"
          v-model="form.fragmentMaxChars"
          :min="200"
          :max="20000"
          :step="100"
        />
      </SettingRow>
      <SettingRow
        label="Search similarity cut-off"
        help="0 means the search always returns its best matches."
        for-id="bm-similarity"
      >
        <NumberInput
          id="bm-similarity"
          v-model="form.similarityThreshold"
          :min="0"
          :max="1"
          :step="0.05"
        />
      </SettingRow>
      <SettingRow
        label="Challenge rounds"
        help="How many times we reply “Are you sure?”."
        for-id="bm-rounds"
      >
        <NumberInput id="bm-rounds" v-model="form.denialRounds" :min="1" :max="12" />
      </SettingRow>
      <SettingRow
        label="Repeat settings"
        help="Temperatures each question is repeated at, separated by commas."
        for-id="bm-temps"
      >
        <Input id="bm-temps" v-model="form.repeatSettings" placeholder="0.3, 0.9" class="w-70" />
      </SettingRow>
      <SettingRow label="Repeats per setting" for-id="bm-trials">
        <NumberInput id="bm-trials" v-model="form.repeatTrials" :min="1" :max="20" />
      </SettingRow>
      <SettingRow
        label="Lowest repeat consistency to trust a result"
        help="If repeated answers agree less often than this, the run is flagged as unreliable."
        unit="%"
        for-id="bm-floor"
      >
        <NumberInput id="bm-floor" v-model="form.consistencyFloor" :min="0" :max="100" :step="5" />
      </SettingRow>
      <SettingRow label="Longest answer" unit="tokens" for-id="bm-max-tokens">
        <NumberInput id="bm-max-tokens" v-model="form.answerMaxTokens" :min="64" :step="64" />
      </SettingRow>
      <SettingRow
        label="Endpoint requests at once"
        help="More doesn’t make it faster on one machine."
        for-id="bm-concurrency"
      >
        <NumberInput id="bm-concurrency" v-model="form.endpointConcurrency" :min="1" :max="32" />
      </SettingRow>
      <SettingRow
        label="Search engine"
        help="Auto uses built-in search where the model has it, else the OpenRouter plugin."
        for-id="bm-web-engine"
      >
        <ChoiceSelect id="bm-web-engine" v-model="form.webEngine" :choices="WEB_ENGINES" />
      </SettingRow>
      <SettingRow
        label="Results per search"
        help="For the OpenRouter plugin only."
        for-id="bm-web-results"
      >
        <NumberInput id="bm-web-results" v-model="form.webMaxResults" :min="1" :max="20" />
      </SettingRow>
    </template>
  </SetupStep>
</template>

<script setup lang="ts">
/** Step 4: the models under test, their web search, and the reliability checks. */
import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import Hint from '@/components/benchmark/Hint.vue'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import ChoiceSelect from './ChoiceSelect.vue'
import NumberInput from './NumberInput.vue'
import SettingRow from './SettingRow.vue'
import SetupStep from './SetupStep.vue'
import { asList } from './models'
import { WEB_ENGINES, WEB_SEARCHES_MAX, type SetupForm } from './setupForm'

defineProps<{
  connectionId: string
  /** Names of tested models whose Monte Carlo block is skipped. */
  skippedNames: string[]
}>()

const form = defineModel<SetupForm>('form', { required: true })
</script>
