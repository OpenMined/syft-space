<template>
  <section v-if="data" class="space-y-6" data-testid="screen-RunMethodPage">
    <div class="space-y-0.5">
      <h1 class="heading-3">How this run was tested</h1>
      <p class="text-sm text-muted-foreground">
        The settings used in the run of {{ day }}. Another run can use different settings.
      </p>
    </div>

    <div class="flex max-w-[53.75rem] flex-col gap-7 text-sm">
      <section class="space-y-2.5" aria-labelledby="settings-title">
        <h2 id="settings-title" class="text-base font-semibold">Settings for this run</h2>
        <dl class="overflow-hidden rounded-lg border border-border bg-card">
          <div
            v-for="row in settings"
            :key="row.key"
            class="flex items-start gap-4 border-b border-border px-4 py-3 last:border-b-0"
            :data-testid="`setting-${row.key}`"
          >
            <dt class="flex w-32 shrink-0 items-center gap-1.5 font-semibold sm:w-[14.375rem]">
              {{ row.label }}
              <InfoTip v-if="row.tip" :text="row.tip" />
            </dt>
            <dd class="min-w-0 flex-1 text-muted-foreground">{{ row.value ?? DASH }}</dd>
          </div>
        </dl>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">1. Where the questions came from</h2>
        <p class="text-muted-foreground">
          An AI model running inside your Syft Space read the articles you published{{
            windowPhrase
          }}
          and wrote questions from them. Each question has one correct answer taken from your
          reporting, and is used in this run only.
        </p>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">2. Removing what the web already knows</h2>
        <p class="text-muted-foreground" data-testid="web-check">
          A separate model with web search tried every question. If it could answer one, that
          question was removed, because the answer is not unique to your reporting.{{
            funnelPhrase
          }}
        </p>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">3. Kinds of question</h2>
        <div class="overflow-x-auto rounded-lg border border-border bg-card">
          <table class="w-full min-w-[42.5rem]">
            <thead class="bg-muted/40 text-xs text-muted-foreground">
              <tr class="border-b border-border">
                <th scope="col" class="px-4 py-2.5 text-left font-medium">Kind</th>
                <th scope="col" class="px-4 py-2.5 text-left font-medium">
                  What it asks the model to do
                </th>
                <th scope="col" class="px-4 py-2.5 text-right font-medium">Asked</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="k in kinds"
                :key="k.generator"
                class="border-b border-border last:border-b-0"
                data-testid="kind-row"
              >
                <th scope="row" class="w-56 px-4 py-3 text-left font-semibold">{{ k.label }}</th>
                <td class="px-4 py-3">{{ k.description }}</td>
                <td class="w-20 px-4 py-3 text-right text-muted-foreground tabular-nums">
                  {{ count(k.asked) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">4. How each model was asked</h2>
        <p class="text-muted-foreground">
          Every model answered every question twice.
          <b class="font-semibold text-foreground">On its own</b>, it could use web search as usual.
          <b class="font-semibold text-foreground">With your data</b>, it was also sent the most
          relevant excerpts from your archive. The difference between the two is what your data
          adds.
        </p>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">5. How answers were graded</h2>
        <dl class="overflow-hidden rounded-lg border border-border bg-card">
          <div
            v-for="g in GRADES"
            :key="g.verdict"
            class="flex items-start gap-4 border-b border-border px-4 py-3 last:border-b-0"
          >
            <dt class="w-32 shrink-0 sm:w-[14.375rem]">
              <Badge variant="outline" :class="verdictTone(g.verdict)">
                {{ verdictLabel(g.verdict) }}
              </Badge>
            </dt>
            <dd class="min-w-0 flex-1 text-muted-foreground">{{ g.text }}</dd>
          </div>
        </dl>
        <p class="text-muted-foreground">
          AI judges from different companies graded each answer and recorded their reasons. A judge
          does not grade a model from its own company.
        </p>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">6. Reliability checks</h2>
        <p class="text-muted-foreground" data-testid="checks-text">{{ checksText }}</p>
      </section>

      <section class="space-y-2.5">
        <h2 class="text-base font-semibold">7. What left your organization</h2>
        <p class="text-muted-foreground">
          Questions were written inside your Syft Space. The excerpts from your archive were sent to
          the models being tested, only to answer these questions. Scores leave only if you publish
          them, and questions and articles never do.
        </p>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import InfoTip from '../InfoTip.vue'
import { useRun } from './context'
import { count, DASH, dayTime } from './figures'
import { kindDescription, kindLabel, verdictLabel, verdictTone } from './labels'
import {
  kindAsked,
  methodKinds,
  methodSettings,
  repeatsTotal,
  utcStamp,
  webRemoved,
} from './selectors'

const GRADES = [
  { verdict: 'correct', text: 'The answer matches your reporting.' },
  { verdict: 'abstain', text: 'The model said it could not answer.' },
  { verdict: 'hallucinate', text: 'The model gave an answer your reporting does not support.' },
] as const

const { data } = useRun()

const day = computed(() => dayTime(utcStamp(data.value?.run.created_at)).split(', ')[0])

const settings = computed(() => (data.value ? methodSettings(data.value) : []))

const windowPhrase = computed(() => {
  const days = data.value?.run.window_days
  if (typeof days !== 'number' || days <= 0) return ''
  return ` in the ${days === 1 ? '24 hours' : `${days} days`} before the run`
})

const funnelPhrase = computed(() => {
  if (!data.value) return ''
  const { written, asked } = data.value.funnel
  const removed = webRemoved(data.value)
  if (written === null || removed === null) return ''
  return ` Of ${count(written)} questions written, ${count(removed)} were removed and ${count(asked)} were asked.`
})

const kinds = computed(() => {
  const report = data.value
  if (!report) return []
  return methodKinds(report).map((generator) => ({
    generator,
    label: kindLabel(generator),
    description: kindDescription(generator),
    asked: kindAsked(report, generator),
  }))
})

const checksText = computed(() => {
  const method = data.value?.method
  if (!method) return ''
  const parts: string[] = []
  if (method.denial_rounds)
    parts.push(
      `Right answers were challenged with “Are you sure?” up to ${method.denial_rounds} ${
        method.denial_rounds === 1 ? 'time' : 'times'
      }.`,
    )
  const repeats = repeatsTotal(data.value!)
  if (repeats)
    parts.push(
      `Every question was asked again ${repeats} more ${repeats === 1 ? 'time' : 'times'}.`,
    )
  parts.push(
    'Trick questions with no answer in your reporting tested whether a model would refuse rather than hallucinate.',
  )
  return parts.join(' ')
})
</script>
