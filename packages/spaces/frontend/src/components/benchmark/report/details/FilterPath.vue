<script setup lang="ts">
/** Everything a question went through after it was written, and where it stands now. */
import { computed } from 'vue'
import Hint from '../../Hint.vue'
import { outcomeLabel, outcomeTone } from '../../filter'
import Exchange from './Exchange.vue'
import FilterStep from './FilterStep.vue'
import { statusLabel, type DraftView } from './writing'

const props = defineProps<{ draft: DraftView }>()

const entity = computed(() => props.draft.entity)
const status = computed(() => statusLabel(props.draft.status, props.draft.statusReason))
</script>

<template>
  <ol class="space-y-3" data-testid="filter-path">
    <li v-if="entity" class="space-y-2" data-testid="entity-step">
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="font-semibold">Entity check</span>
        <span
          v-if="entity.outcome"
          class="rounded px-1.5 py-0.5"
          :class="outcomeTone(entity.outcome)"
          >{{ outcomeLabel(entity.outcome) }}</span
        >
        <Hint v-for="(e, n) in entity.entities" :key="n" :text="e.why">
          <span
            class="cursor-help rounded border px-1.5 py-0.5"
            :class="e.identifiable ? 'border-border' : 'border-destructive text-destructive'"
            >{{ e.name }}</span
          >
        </Hint>
      </div>
      <Exchange
        v-if="draft.entityCall"
        title="Entity check call"
        :model="draft.entityCall.model"
        :system="draft.entityCall.system"
        :prompt="draft.entityCall.prompt"
        :reply="draft.entityCall.reply"
        :cost-usd="draft.entityCall.costUsd"
        :latency-s="draft.entityCall.latencyS"
      />
    </li>
    <FilterStep v-for="(step, n) in draft.steps" :key="`${step.stage}-${n}`" :step="step" />
    <li class="flex flex-wrap items-baseline gap-2 text-xs" data-testid="final-status">
      <span class="font-semibold">Status</span>
      <Hint :text="draft.statusNote">
        <span>{{ status }}</span>
      </Hint>
    </li>
  </ol>
</template>
