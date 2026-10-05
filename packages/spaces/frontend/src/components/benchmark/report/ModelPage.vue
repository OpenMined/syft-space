<template>
  <section v-if="!report" data-testid="screen-ModelPage">
    <p class="py-4 text-sm text-muted-foreground" data-testid="model-missing">
      This model is not part of this run.
    </p>
  </section>

  <section v-else class="space-y-6" data-testid="screen-ModelPage">
    <div class="space-y-0.5">
      <h1 class="heading-3">{{ name }}</h1>
      <p class="max-w-[780px] text-sm text-muted-foreground" data-testid="model-subtitle">
        {{ subtitle }}
      </p>
    </div>

    <div
      class="grid grid-cols-1 rounded-lg border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-border"
      data-testid="model-stats"
    >
      <div class="flex flex-col gap-0.5 px-5 py-4">
        <b class="text-2xl font-semibold text-primary tabular-nums">{{
          outOf(report.right_with)
        }}</b>
        <span class="text-sm text-muted-foreground">right with your data</span>
      </div>
      <div class="flex flex-col gap-0.5 px-5 py-4">
        <b class="text-2xl font-semibold tabular-nums">{{ outOf(report.right_alone) }}</b>
        <span class="text-sm text-muted-foreground">right on its own</span>
      </div>
      <div class="flex flex-col gap-0.5 px-5 py-4">
        <b class="text-2xl font-semibold text-primary tabular-nums">{{ liftText }}</b>
        <span class="text-sm text-muted-foreground">added by your data</span>
      </div>
    </div>

    <section class="space-y-2.5" aria-labelledby="answered-title">
      <h2 id="answered-title" class="text-base font-semibold">How it answered</h2>
      <p class="text-sm text-muted-foreground">
        Every answer is graded right, didn’t know, or hallucinated.
      </p>
      <div class="flex flex-col gap-[18px] rounded-lg border border-border bg-card px-5 py-4">
        <div
          v-for="arm in arms"
          :key="arm.key"
          class="flex flex-wrap items-center gap-x-5 gap-y-2"
          :data-testid="`answered-${arm.key}`"
        >
          <b class="w-[200px] shrink-0 text-sm font-medium">{{ arm.label }}</b>
          <div class="flex min-w-0 flex-[1_1_20rem] flex-col gap-1.5">
            <div
              class="flex h-[18px] gap-0.5 overflow-hidden rounded"
              role="img"
              :aria-label="arm.aria"
            >
              <span
                v-for="part in arm.parts"
                v-show="part.n"
                :key="part.key"
                class="block"
                :class="part.bar"
                :style="{ width: share(part.n) }"
              />
            </div>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span v-for="part in arm.parts" :key="part.key">
                <b class="font-semibold tabular-nums" :class="part.text">{{ part.n }}</b>
                {{ part.label }}
              </span>
            </div>
          </div>
        </div>
        <p class="border-t border-border pt-3 text-sm" data-testid="answered-foot">
          {{ hallucinationText }}
        </p>
      </div>
    </section>

    <section class="space-y-2.5" aria-labelledby="kinds-title">
      <h2 id="kinds-title" class="text-base font-semibold">Where your data helped most</h2>
      <p class="text-sm text-muted-foreground">Right answers by kind of question.</p>
      <div class="overflow-x-auto rounded-lg border border-border bg-card">
        <table class="w-full min-w-[680px] text-sm">
          <thead class="bg-muted/40 text-xs text-muted-foreground">
            <tr class="border-b border-border">
              <th scope="col" class="px-4 py-2.5 text-left font-medium">Kind of question</th>
              <th scope="col" class="w-[88px] px-2 py-2.5 text-right font-medium">Asked</th>
              <th scope="col" class="w-[88px] px-2 py-2.5 text-right font-medium">On its own</th>
              <th scope="col" class="w-[120px] px-2 py-2.5 text-right font-medium">
                With your data
              </th>
              <th scope="col" class="w-[38%] px-4 py-2.5 text-left font-medium">Difference</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="k in kinds"
              :key="k.generator"
              class="border-b border-border last:border-b-0"
              data-testid="kind-row"
            >
              <td class="px-4 py-3">{{ kindLabel(k.generator) }}</td>
              <td class="px-2 py-3 text-right text-muted-foreground tabular-nums">
                {{ count(k.asked) }}
              </td>
              <td class="px-2 py-3 text-right text-muted-foreground tabular-nums">
                {{ pct(k.rate_alone) }}
              </td>
              <td class="px-2 py-3 text-right tabular-nums">{{ pct(k.rate_with) }}</td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2.5">
                  <span class="block h-2 flex-1 overflow-hidden rounded bg-muted">
                    <span
                      v-if="k.lift !== null"
                      class="block h-full rounded bg-primary"
                      data-testid="kind-bar"
                      :style="{ width: `${Math.min(Math.max(k.lift, 0), 100)}%` }"
                    />
                  </span>
                  <b class="w-10 shrink-0 text-right font-semibold text-primary tabular-nums">
                    {{ points(k.lift) }}
                  </b>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="space-y-2.5" aria-labelledby="closer-title">
      <h2 id="closer-title" class="text-base font-semibold">Look closer</h2>
      <div class="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
        <RouterLink
          v-for="link in links"
          :key="link.key"
          :to="link.to"
          class="flex items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-muted/40"
          :data-testid="`link-${link.key}`"
        >
          <span class="flex min-w-0 flex-col gap-0.5">
            <b class="text-sm font-medium">{{ link.title }}</b>
            <span class="text-sm text-muted-foreground">{{ link.text }}</span>
          </span>
          <ChevronRight class="size-[18px] shrink-0 text-muted-foreground" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import type { BenchmarkTally } from '@/api/types'
import { useRun } from './context'
import { count, DASH, pct, points } from './figures'
import { kindLabel, modelName, vendorName } from './labels'
import { checksLocation, questionsLocation } from './routing'
import { isTrick } from './selectors'

const run = useRun()

const report = computed(() => run.modelReport.value)
const name = computed(() => (run.model.value ? modelName(run.model.value) : ''))
const asked = computed(() => report.value?.asked ?? 0)

const subtitle = computed(() => {
  const vendor = run.model.value ? vendorName(run.model.value) : null
  const text = `asked the same ${asked.value} questions twice: on its own, and with your data`
  return vendor ? `${vendor} · ${text}` : text.charAt(0).toUpperCase() + text.slice(1)
})

function outOf(n: number): string {
  return `${n} of ${asked.value}`
}

function share(n: number): string {
  return asked.value ? `${(n / asked.value) * 100}%` : '0%'
}

const liftText = computed(() => {
  const lift = report.value?.lift ?? null
  return lift === null ? DASH : `${points(lift)} points`
})

const PARTS = [
  { key: 'correct', label: 'right', bar: 'bg-primary', text: 'text-foreground' },
  { key: 'abstain', label: 'didn’t know', bar: 'bg-muted-foreground/30', text: 'text-foreground' },
  {
    key: 'hallucinate',
    label: 'hallucinated',
    bar: 'bg-warning',
    text: 'text-amber-700 dark:text-amber-400',
  },
] as const

function parts(t: BenchmarkTally) {
  return PARTS.map((p) => ({ ...p, n: t[p.key] }))
}

const arms = computed(() => {
  const r = report.value
  if (!r) return []
  return [
    { key: 'with', label: 'With your data', tally: r.tally.with },
    { key: 'alone', label: 'On its own', tally: r.tally.alone },
  ].map((a) => {
    const ps = parts(a.tally)
    return {
      key: a.key,
      label: a.label,
      parts: ps,
      aria: `${a.label}: ${ps.map((p) => `${p.n} ${p.label}`).join(', ')}`,
    }
  })
})

const hallucinationText = computed(() => {
  const r = report.value
  if (!r) return ''
  const before = r.tally.alone.hallucinate
  const after = r.tally.with.hallucinate
  const verb = after < before ? 'fell' : 'went'
  return `Hallucinations ${verb} from ${before} to ${after} when the model had your data.`
})

const kinds = computed(() => (report.value?.kinds ?? []).filter((k) => !isTrick(k.generator)))

const links = computed(() => {
  const model = run.model.value ?? ''
  return [
    {
      key: 'questions',
      to: questionsLocation(run.jobId, model),
      title: 'Every question and answer',
      text: `All ${asked.value} questions, both of the model’s answers, and what each judge decided and why`,
    },
    {
      key: 'checks',
      to: checksLocation(run.jobId, model),
      title: 'Reliability checks',
      text: 'Whether it held its answers when challenged, answered the same way twice, and refused questions with no answer',
    },
  ]
})
</script>
