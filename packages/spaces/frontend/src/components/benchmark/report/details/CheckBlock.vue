<script setup lang="ts">
/** One check of an arm (asked once, challenged, asked again): its transcript and each judge's call. */
import { computed } from 'vue'
import Hint from '../../Hint.vue'
import Exchange from './Exchange.vue'
import VerdictPill from './VerdictPill.vue'
import { heldOf } from '../selectors'
import { BLOCK_TITLE, type BlockAudit, type JudgeAudit } from './questionAudit'

const props = defineProps<{
  block: BlockAudit
  generator: string
  /** The run's judges, primary first. */
  panel: string[]
}>()

function judgeTitle(judge: JudgeAudit): string {
  const n = props.panel.indexOf(judge.judge)
  return n < 0 ? 'Judge' : `Judge ${n + 1}`
}

const heldText = computed(() => {
  const held = heldOf(props.block.denial)
  return held ? `Held ${held.held} of ${held.of} rounds` : ''
})

/** Whether the round held: every round before the one it gave in on. */
function roundHeld(round: number): boolean {
  const denial = props.block.denial!
  return !denial.flipped || round < (denial.flip_round ?? round + 1)
}

const TONE_OK = 'bg-primary/10'
const TONE_BAD = 'bg-warning/20'
</script>

<template>
  <section
    class="space-y-3 rounded-lg border border-border p-3"
    :data-testid="`block-${block.block}`"
  >
    <h3 class="text-sm font-semibold">{{ BLOCK_TITLE[block.block] ?? block.block }}</h3>

    <div v-if="block.denial" class="space-y-1.5 text-xs" data-testid="denial-log">
      <p class="text-muted-foreground">
        {{ block.denial.flipped ? `Gave in on round ${block.denial.flip_round}` : heldText
        }}<template v-if="block.denial.note"> · {{ block.denial.note }}</template>
      </p>
      <p v-if="!block.denial.log.length" class="text-muted-foreground">Transcript not kept.</p>
      <div v-for="round in block.denial.log" :key="round.round" class="space-y-1">
        <p class="text-muted-foreground italic">{{ round.round }}. {{ round.objection }}</p>
        <p
          class="rounded-md px-2 py-1 break-words whitespace-pre-wrap"
          :class="roundHeld(round.round) ? TONE_OK : TONE_BAD"
          :data-held="roundHeld(round.round)"
          v-text="round.answer"
        />
      </div>
    </div>

    <div v-if="block.repeats" class="space-y-1.5 text-xs" data-testid="repeats-log">
      <p class="text-muted-foreground">
        {{ Math.round(block.repeats.accuracy * 100) }}% right ·
        {{ Math.round(block.repeats.consistency * 100) }}% the same answer
        <template v-if="block.repeats.note"> · {{ block.repeats.note }}</template>
      </p>
      <p v-if="!block.repeats.log.length" class="text-muted-foreground">Transcript not kept.</p>
      <div v-for="trial in block.repeats.log" :key="trial.trial" class="space-y-1">
        <p class="text-muted-foreground">
          Trial {{ trial.trial }} · temperature {{ trial.temperature }} ·
          {{ trial.correct ? 'right' : 'wrong' }}
        </p>
        <p
          class="rounded-md px-2 py-1 break-words whitespace-pre-wrap"
          :class="trial.correct ? TONE_OK : TONE_BAD"
          v-text="trial.answer"
        />
      </div>
    </div>

    <Exchange
      v-for="judge in block.judges"
      :key="judge.judge"
      :title="judgeTitle(judge)"
      :model="judge.judge"
      :system="judge.prompts?.judge_system"
      :prompt="judge.prompts?.judge_prompt"
      :reply="judge.prompts?.judge_raw"
      data-testid="judge"
    >
      <template #aside>
        <span class="flex items-center gap-1.5">
          <Hint
            v-if="judge.primary"
            text="Its verdict is the one counted, unless the owner set one."
          >
            <span
              class="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
              data-testid="primary-judge"
              >primary</span
            >
          </Hint>
          <VerdictPill
            :verdict="judge.row.verdict"
            :generator="generator"
            :behavior="judge.row.behavior"
          />
        </span>
      </template>
      <Hint
        v-if="judge.prompts?.judged_without_model"
        text="An option letter or fill-in matched, or an abstention was recognised by its wording."
      >
        <p class="text-xs text-muted-foreground" data-testid="no-judge-call">No judge call.</p>
      </Hint>
      <p v-else-if="!judge.prompts" class="text-xs text-muted-foreground">Prompts not kept.</p>
      <p
        v-if="judge.row.reasoning"
        class="text-xs break-words whitespace-pre-wrap"
        v-text="judge.row.reasoning"
      />
    </Exchange>
  </section>
</template>
