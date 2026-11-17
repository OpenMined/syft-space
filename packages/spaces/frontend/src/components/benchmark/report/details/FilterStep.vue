<script setup lang="ts">
/** One filter decision: its outcome and reason, the archive check and the web check behind it. */
import { computed } from 'vue'
import { outcomeLabel, outcomeTone, reasonText, stageLabel } from '../../filter'
import CitationLinks from '../CitationLinks.vue'
import { verdictLabel, verdictTone } from '../labels'
import Exchange from './Exchange.vue'
import type { ScreeningStep } from './writing'

const props = defineProps<{ step: ScreeningStep }>()

const reason = computed(() =>
  reasonText({ reason: props.step.reason, reason_code: props.step.reasonCode }),
)
const web = computed(() => props.step.web)
</script>

<template>
  <li class="space-y-2" data-testid="filter-step">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span class="font-semibold">{{ stageLabel(step.stage) }}</span>
      <span class="rounded px-1.5 py-0.5" :class="outcomeTone(step.outcome)">
        {{ outcomeLabel(step.outcome) }}
      </span>
      <span v-if="reason" class="min-w-0 break-words text-muted-foreground">{{ reason }}</span>
    </div>
    <Exchange
      v-if="step.gate"
      title="Archive check"
      :model="step.gate.model"
      :system="step.gate.system"
      :prompt="step.gate.prompt"
      :reply="step.gate.reply"
      :cost-usd="step.gate.costUsd"
      :latency-s="step.gate.latencyS"
    />
    <template v-if="web">
      <Exchange
        title="Web check"
        :model="web.exchange.model"
        :system="web.exchange.system"
        :prompt="web.exchange.prompt"
        :reply="web.exchange.reply"
        :cost-usd="web.exchange.costUsd"
        :latency-s="web.exchange.latencyS"
      >
        <template #aside>
          <span
            v-if="web.verdict"
            class="rounded px-1.5 py-0.5 text-xs"
            :class="verdictTone(web.verdict)"
            data-testid="web-verdict"
            >{{ verdictLabel(web.verdict) }}</span
          >
        </template>
        <CitationLinks
          v-if="web.citations.length"
          :citations="web.citations"
          data-testid="web-citations"
        />
        <p v-if="web.searches !== null" class="text-xs text-muted-foreground">
          {{ web.searches }} {{ web.searches === 1 ? 'search' : 'searches' }}
        </p>
        <p v-if="web.error" class="text-xs break-words text-destructive">{{ web.error }}</p>
      </Exchange>
      <Exchange
        v-if="web.judgeCall"
        title="Web check judge"
        :model="web.judgeCall.model"
        :system="web.judgeCall.system"
        :prompt="web.judgeCall.prompt"
        :reply="web.judgeCall.reply"
        :cost-usd="web.judgeCall.costUsd"
        :latency-s="web.judgeCall.latencyS"
      />
      <p
        v-else-if="web.reasoning"
        class="text-xs text-muted-foreground"
        data-testid="web-reasoning"
      >
        Verdict: {{ web.reasoning }}
      </p>
    </template>
  </li>
</template>
