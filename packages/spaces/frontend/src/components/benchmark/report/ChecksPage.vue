<template>
  <section class="space-y-6" data-testid="screen-ChecksPage">
    <div class="space-y-0.5">
      <h1 class="heading-3">Reliability checks</h1>
      <p class="max-w-[780px] text-sm text-muted-foreground">
        Extra tests on {{ name }}’s answers with your data. They show whether its right answers are
        solid, or could have been luck.
      </p>
    </div>

    <div v-if="rows.length" class="divide-y divide-border rounded-lg border border-border bg-card">
      <div
        v-for="row in rows"
        :key="row.key"
        class="flex flex-wrap gap-x-8 gap-y-4 p-5"
        :data-testid="`check-${row.key}`"
      >
        <div class="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
          <h2 class="text-[15px] font-semibold">{{ row.title }}</h2>
          <p class="text-sm text-muted-foreground">{{ row.what }}</p>
        </div>
        <div class="flex min-w-0 flex-[1_1_360px] flex-col gap-2">
          <div
            v-for="line in row.lines"
            :key="line.label"
            class="flex flex-wrap items-center gap-x-3 gap-y-1 md:flex-nowrap"
            data-testid="check-line"
          >
            <span class="w-24 shrink-0 text-sm text-muted-foreground">{{ line.label }}</span>
            <span
              class="block h-2 basis-full overflow-hidden rounded bg-muted md:flex-1 md:basis-auto"
            >
              <span
                v-if="line.value !== null"
                class="block h-full rounded bg-chart-5"
                :style="{ width: `${Math.min(Math.max(line.value, 0), 1) * 100}%` }"
              />
            </span>
            <b class="w-10 shrink-0 text-right text-sm font-medium tabular-nums">
              {{ pct(line.value) }}
            </b>
          </div>
          <div v-if="row.squares?.length" class="flex flex-wrap gap-1.5" aria-hidden="true">
            <span
              v-for="(outcome, i) in row.squares"
              :key="i"
              class="size-7 rounded border"
              :class="SQUARE_TONE[outcome]"
              :title="BEHAVIOR_LABEL[outcome]"
              data-testid="check-square"
              :data-bad="outcome === 'made_up'"
              :data-outcome="outcome"
            />
          </div>
          <p class="text-sm" data-testid="check-reading">{{ row.reading }}</p>
        </div>
      </div>
    </div>
    <p v-else class="py-4 text-sm text-muted-foreground" data-testid="checks-missing">
      This model is not part of this run.
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BenchmarkRunMethod } from '@/api/types'
import { useRun } from './context'
import { DASH, pct } from './figures'
import { BEHAVIOR_LABEL, modelName, type Behavior } from './labels'
import { trickReading, trickSquares } from './selectors'

const SQUARE_TONE: Record<Behavior, string> = {
  made_up: 'border-warning bg-warning/15',
  web_sourced: 'border-sky-500 bg-sky-500/10',
  declined: 'border-primary bg-primary/10',
  corrected: 'border-primary bg-primary/10',
}

interface Line {
  label: string
  value: number | null
}

interface CheckRow {
  key: string
  title: string
  what: string
  lines: Line[]
  squares?: Behavior[]
  reading: string
}

const run = useRun()

const name = computed(() => (run.model.value ? modelName(run.model.value) : 'the model'))

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

const TIMES = ['', 'once', 'twice', 'three times', 'four times']

function times(n: number): string {
  return TIMES[n] ?? `${n} times`
}

/** `trials` is repeats per temperature. */
function repeatsText(repeats: BenchmarkRunMethod['repeats']): string {
  const settings = repeats?.temperatures.length ?? 0
  if (!repeats || !settings) return `Each question was asked ${DASH} more times.`
  const total = repeats.trials * settings
  if (settings === 2) {
    const each = times(repeats.trials)
    return `Each question was asked ${total} more times, ${each} at a steady setting and ${each} at a looser one.`
  }
  if (settings === 1) return `Each question was asked ${total} more times at the same setting.`
  return `Each question was asked ${total} more times, ${times(repeats.trials)} at each of ${settings} settings.`
}

function judgesList(judges: string[]): string {
  const named = judges.map((j, i) => `Judge ${i + 1} (${modelName(j)})`)
  if (named.length < 2) return named.join('')
  return `${named.slice(0, -1).join(', ')} and ${named[named.length - 1]}`
}

const rows = computed<CheckRow[]>(() => {
  const report = run.modelReport.value
  const data = run.data.value
  if (!report || !data) return []
  const c = report.checks

  const rounds = c.challenged ? c.held_by_round : []
  const limit = c.denial_limit ?? (c.held_by_round.length || null)
  const held: CheckRow = {
    key: 'challenged',
    title: 'Holding a right answer when challenged',
    what: `After each right answer we replied “Are you sure?”, up to ${limit ?? DASH} times. Share still giving the right answer:`,
    lines: c.challenged
      ? [
          { label: 'First answer', value: 1 },
          ...rounds.map((v, k) => ({ label: `After round ${k + 1}`, value: v })),
        ]
      : [],
    reading: `Gave up a right answer at some point on ${pct(
      c.challenged && c.kept_right !== null ? 1 - c.kept_right : null,
    )} of questions.`,
  }

  const temps = [...c.by_temperature].sort((a, b) => a.t - b.t)
  const same: CheckRow = {
    key: 'repeated',
    title: 'Answering the same way twice',
    what: repeatsText(data.method.repeats),
    lines: [
      { label: 'Steady', value: temps[0]?.accuracy ?? null },
      { label: 'Looser', value: temps.length > 1 ? temps[temps.length - 1]!.accuracy : null },
    ],
    reading: `Gave the same answer every time on ${pct(c.repeated ? c.same_answer : null)} of questions.`,
  }

  const trick: CheckRow = {
    key: 'trick',
    title: 'Refusing questions with no answer',
    what: `${plural(c.trick_asked, 'trick question', 'trick questions')} asked for details your reporting does not contain. The right response is “I don’t know”.`,
    lines: [],
    squares: trickSquares(c.trick_asked, c.trick_answered, c.trick_web ?? 0),
    reading: trickReading(c.trick_asked, c.trick_answered, c.trick_web ?? 0),
  }

  const search: CheckRow = {
    key: 'search',
    title: 'Finding the right passage',
    what: 'With your data, the model gets the most relevant excerpts from a search of your archive. This checks the search, not the model, so it is the same for every model.',
    lines: [{ label: 'Found', value: c.searched ? c.search_found : null }],
    reading: c.searched
      ? `On ${plural(c.missed, 'question', 'questions')} the source paragraph was not among the excerpts.`
      : DASH,
  }

  const judges: CheckRow = {
    key: 'judges',
    title: 'Judges agreeing',
    what: data.judges.length ? `${judgesList(data.judges)} graded every answer.` : DASH,
    lines: [{ label: 'Agreed', value: c.answers ? c.agreement : null }],
    reading:
      c.answers && c.agreement !== null
        ? `They disagreed on ${c.answers - c.judges_agreed} of ${plural(c.answers, 'answer', 'answers')}.`
        : DASH,
  }

  return [held, same, trick, search, judges]
})
</script>
