<script setup lang="ts">
/** The Generate and Filter phases of one job, for a job that asked no model. */
import { ref } from 'vue'
import FilterList from './FilterList.vue'
import PairList from './PairList.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

defineProps<{ slug: string; job: string }>()

const phase = ref('generate')

const TAB =
  'flex-none inline-flex items-center gap-2 h-9 px-3 rounded-none border-0 border-b-2 ' +
  'border-b-transparent bg-transparent shadow-none text-muted-foreground hover:text-foreground ' +
  'data-[state=active]:bg-transparent dark:data-[state=active]:bg-transparent ' +
  'data-[state=active]:text-primary dark:data-[state=active]:text-primary ' +
  'data-[state=active]:border-b-primary data-[state=active]:shadow-none -mb-px'
</script>

<template>
  <Tabs v-model="phase" class="space-y-0" data-testid="build-phases">
    <TabsList
      class="h-auto bg-transparent rounded-none p-0 w-full justify-start gap-2 border-b border-border/50"
    >
      <TabsTrigger value="generate" :class="TAB">Generate</TabsTrigger>
      <TabsTrigger value="filter" :class="TAB">Filter</TabsTrigger>
    </TabsList>
    <TabsContent value="generate" class="pt-4 mt-0">
      <PairList :slug="slug" :job="job" :refresh-key="0" />
    </TabsContent>
    <TabsContent value="filter" class="pt-4 mt-0">
      <FilterList :slug="slug" :job="job" />
    </TabsContent>
  </Tabs>
</template>
