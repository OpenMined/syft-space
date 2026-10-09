<script setup lang="ts">
/**
 * One run on its own, with everything this Space knows about it.
 *
 * It opens in place of the list rather than beside it: the question here is no
 * longer "which of these runs speaks for my endpoint" — that was answered by
 * getting this far — but "what exactly did this one do", and the runs around it
 * are noise against that.
 *
 * The figures at the top are the same figures the list shows, and deliberately
 * not in a card: a card is a thing among other things, one of a stack, with a
 * lid because the stack would be unreadable otherwise. Here there is nothing to
 * stack it against and nothing to fold it away from — so it is simply this
 * page's heading and this page's numbers, with the one decision they support
 * beside them rather than at the end of a scroll.
 *
 * Under them, the run phase by phase — execution and judging together, since a
 * verdict and the answer it is about are one fact. Each tab shows what that
 * phase left behind, and only for this launch, which is what the `job` on the
 * card is for. A card that names no launch (a run started outside the queue, or
 * one older than the job table) has no phases to show, and says so rather than
 * showing the endpoint's whole history under the heading of one run.
 */
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { ArrowLeft, Megaphone } from 'lucide-vue-next'

import AnswerList from './AnswerList.vue'
import FilterList from './FilterList.vue'
import KindTable from './KindTable.vue'
import CardCharts from './CardCharts.vue'
import CardFigures from './CardFigures.vue'
import PairList from './PairList.vue'
import TimingTable from './TimingTable.vue'
import VisibleAt from './VisibleAt.vue'
import type { RunMarketplace } from './runs'
import { saveRunExport } from './report/useRunReport'
import { apiErrorDetail } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{
  slug: string
  /** Null for a job that asked no model: only its phases are shown. */
  card: BenchmarkCard | BenchmarkReport | null
  /** The launch, when the card does not name it. */
  jobId?: string
  measured: string
  published: boolean
  marketplaces?: RunMarketplace[]
  busy?: boolean
  working?: boolean
}>()

const emit = defineEmits<{ back: []; publish: []; retract: [] }>()

/** The launch behind this card; empty where the run belongs to none. */
const job = computed(() => props.card?.job ?? props.jobId ?? '')

const phase = ref('generate')

const exporting = ref(false)

async function downloadExcel(): Promise<void> {
  exporting.value = true
  try {
    await saveRunExport(props.slug, job.value)
  } catch (e) {
    toast.error(apiErrorDetail(e, 'Could not download the Excel file'))
  } finally {
    exporting.value = false
  }
}

/** Bumped to make a list refetch; the lists watch it. */
const refreshKey = ref(0)

const TAB =
  'flex-none inline-flex items-center gap-2 h-9 px-3 rounded-none border-0 border-b-2 ' +
  'border-b-transparent bg-transparent shadow-none text-muted-foreground hover:text-foreground ' +
  'data-[state=active]:bg-transparent dark:data-[state=active]:bg-transparent ' +
  'data-[state=active]:text-primary dark:data-[state=active]:text-primary ' +
  'data-[state=active]:border-b-primary data-[state=active]:shadow-none -mb-px'
</script>

<template>
  <div class="space-y-4">
    <div>
      <Button variant="ghost" size="sm" class="h-8 px-2 -ml-2" @click="emit('back')">
        <ArrowLeft class="h-4 w-4 mr-1.5" />
        Back
      </Button>
    </div>

    <div class="flex items-center gap-3 flex-wrap">
      <Megaphone v-if="published" class="h-4 w-4 shrink-0 text-primary" />
      <h2 class="text-sm font-medium text-foreground">
        Benchmark Details
        <span class="text-muted-foreground font-normal">{{ measured }}</span>
      </h2>

      <div v-if="card || job" class="ml-auto flex items-center gap-2 shrink-0">
        <Button
          v-if="job"
          variant="outline"
          size="sm"
          class="h-7 px-2.5 text-xs"
          :disabled="exporting"
          data-testid="download-excel"
          @click="downloadExcel"
        >
          {{ exporting ? 'Preparing…' : 'Download Excel' }}
        </Button>
        <template v-if="card">
          <VisibleAt v-if="published && marketplaces?.length" :marketplaces="marketplaces" />
          <span class="text-xs" :class="published ? 'text-primary' : 'text-muted-foreground'">
            {{ published ? 'Public' : 'Private' }}
          </span>
          <Button
            v-if="published"
            variant="outline"
            size="sm"
            class="h-7 px-2.5 text-xs"
            :disabled="busy"
            @click="emit('retract')"
          >
            {{ working ? 'Working…' : 'Unpublish' }}
          </Button>
          <Button
            v-else
            size="sm"
            class="h-7 px-2.5 text-xs"
            :disabled="busy"
            @click="emit('publish')"
          >
            {{ working ? 'Working…' : 'Publish' }}
          </Button>
        </template>
      </div>
    </div>

    <template v-if="card">
      <CardFigures :card="card" />

      <CardCharts
        :answerable="card.answerable"
        :models="card.models"
        :skills="card.skills"
        :pressure="card.pressure"
        :stability="card.stability"
      />

      <hr class="border-border/60" />
    </template>

    <TimingTable v-if="job" :slug="slug" :job="job" :refresh-key="refreshKey" />

    <p v-if="!job" class="text-xs text-muted-foreground">
      This run belongs to no launch the benchmark can name, so there is nothing to show phase by
      phase.
    </p>

    <Tabs v-else v-model="phase" class="space-y-0">
      <TabsList
        class="h-auto bg-transparent rounded-none p-0 w-full justify-start gap-2 border-b border-border/50"
      >
        <TabsTrigger value="generate" :class="TAB">Generate</TabsTrigger>
        <TabsTrigger value="filter" :class="TAB">Filter</TabsTrigger>
        <TabsTrigger value="execute" :class="TAB">Execute &amp; Judge</TabsTrigger>
      </TabsList>

      <!-- What this launch built, screened ones included: a rejected question
           is part of what generation did, and taking it out of the list would
           leave the owner unable to put it back. -->
      <TabsContent value="generate" class="pt-4 mt-0 space-y-3">
        <KindTable :slug="slug" :job="job" :refresh-key="refreshKey" />
        <PairList :slug="slug" :job="job" :refresh-key="refreshKey" />
      </TabsContent>

      <TabsContent value="filter" class="pt-4 mt-0">
        <FilterList :slug="slug" :job="job" :refresh-key="refreshKey" />
      </TabsContent>

      <!-- One tab, because an answer and the verdicts on it are one fact:
           split in two, each tab showed the same rows and said half of it. -->
      <TabsContent value="execute" class="pt-4 mt-0">
        <AnswerList :slug="slug" :job="job" :refresh-key="refreshKey" />
      </TabsContent>
    </Tabs>
  </div>
</template>
