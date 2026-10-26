<script setup lang="ts">
/** One run in detail: its figures, timing, and each phase's data for its job. */
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { ArrowLeft } from 'lucide-vue-next'

import AnswerList from './AnswerList.vue'
import FilterList from './FilterList.vue'
import KindTable from './KindTable.vue'
import CardCharts from './CardCharts.vue'
import CardFigures from './CardFigures.vue'
import PairList from './PairList.vue'
import TimingTable from './TimingTable.vue'
import { saveRunExport } from './report/useRunReport'
import { apiErrorDetail } from '@/lib/errors'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{
  slug: string
  /** Null for a job that asked no model: only its phases are shown. */
  card: BenchmarkCard | BenchmarkReport | null
  /** The job, when the card does not name it. */
  jobId?: string
  measured: string
}>()

const emit = defineEmits<{ back: [] }>()

/** The run's job; empty when there is none. */
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
      <h2 class="text-sm font-medium text-foreground">
        Benchmark Details
        <span class="text-muted-foreground font-normal">{{ measured }}</span>
      </h2>

      <div v-if="job" class="ml-auto flex items-center gap-2 shrink-0">
        <Button
          variant="outline"
          size="sm"
          class="h-7 px-2.5 text-xs"
          :disabled="exporting"
          data-testid="download-excel"
          @click="downloadExcel"
        >
          {{ exporting ? 'Preparing…' : 'Download Excel' }}
        </Button>
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

    <TimingTable v-if="job" :slug="slug" :job="job" />

    <p v-if="!job" class="text-xs text-muted-foreground">
      This run has no job, so there is no phase data to show.
    </p>

    <Tabs v-else v-model="phase" class="space-y-0">
      <TabsList
        class="h-auto bg-transparent rounded-none p-0 w-full justify-start gap-2 border-b border-border/50"
      >
        <TabsTrigger value="generate" :class="TAB">Generate</TabsTrigger>
        <TabsTrigger value="filter" :class="TAB">Filter</TabsTrigger>
        <TabsTrigger value="execute" :class="TAB">Execute &amp; Judge</TabsTrigger>
      </TabsList>

      <TabsContent value="generate" class="pt-4 mt-0 space-y-3">
        <KindTable :slug="slug" :job="job" />
        <PairList :slug="slug" :job="job" />
      </TabsContent>

      <TabsContent value="filter" class="pt-4 mt-0">
        <FilterList :slug="slug" :job="job" />
      </TabsContent>

      <TabsContent value="execute" class="pt-4 mt-0">
        <AnswerList :slug="slug" :job="job" />
      </TabsContent>
    </Tabs>
  </div>
</template>
