<script setup lang="ts">
/**
 * One run of the benchmark, as a card the owner can open or leave shut.
 *
 * Every run is the same card, which is the point: the figures sit in the same
 * places, so two runs are compared by looking down the page rather than by
 * reading each one. The newest is open, the rest are a stack of headers — a
 * page that opened six runs at once would bury the one that is published.
 *
 * The header says what the run IS: when it was measured, and whether it speaks
 * for this endpoint right now. It stays visible while the card is shut, because
 * "which run is public" is the question this page exists to answer. What
 * CHANGES that is at the foot, with the other thing that leaves this card —
 * state where the reader looks first, actions where they are reached after
 * reading, and never one word doing both jobs.
 */
import { ref, watch } from 'vue'
import { Archive, ChevronRight, Megaphone } from 'lucide-vue-next'

import CardCharts from './CardCharts.vue'
import CardFigures from './CardFigures.vue'
import VisibleAt from './VisibleAt.vue'
import { Button } from '@/components/ui/button'
import type { RunMarketplace } from './runs'
import type { BenchmarkCard, BenchmarkReport } from '@/api/types'

const props = defineProps<{
  /** The figures themselves — a stored card, or the build that has not been reported yet. */
  card: BenchmarkCard | BenchmarkReport
  /** When the benchmark that produced them ran, already in words. */
  measured: string
  /** Whether this is the run the outside world currently sees. */
  published: boolean
  /** Marketplaces showing it — only ever filled for the published run. */
  marketplaces?: RunMarketplace[]
  /** Open on first draw. The newest run is; the ones behind it are not. */
  defaultOpen?: boolean
  /** Something is being published or withdrawn — every button waits. */
  busy?: boolean
  /** What this card's own button is doing right now, if anything. */
  working?: boolean
}>()

const emit = defineEmits<{ publish: []; retract: []; more: [] }>()

/**
 * Shut unless this is the newest run — and it follows that as long as nobody
 * has said otherwise.
 *
 * The list can reorder under a card after it is drawn: an unreported run
 * arrives, or publishing an earlier one moves what stands where. A card that
 * has been clicked keeps whatever its owner left it at; one that has not obeys
 * its place in the list.
 */
const open = ref(props.defaultOpen ?? false)
const touched = ref(false)

watch(
  () => props.defaultOpen,
  (wanted) => {
    if (!touched.value) open.value = wanted ?? false
  },
)

function toggle(): void {
  touched.value = true
  open.value = !open.value
}
</script>

<template>
  <section class="border border-border/60 rounded-lg overflow-hidden">
    <!-- The header. Always visible, shut or open. -->
    <div
      class="flex items-center gap-3 p-3 sm:p-4 cursor-pointer select-none hover:bg-muted/30"
      role="button"
      tabindex="0"
      :aria-expanded="open"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <ChevronRight
        class="h-4 w-4 text-muted-foreground shrink-0 transition-transform"
        :class="{ 'rotate-90': open }"
      />
      <component
        :is="published ? Megaphone : Archive"
        class="h-4 w-4 shrink-0"
        :class="published ? 'text-primary' : 'text-muted-foreground'"
      />

      <div class="min-w-0">
        <div class="text-sm font-medium text-foreground truncate">
          Benchmark Result
          <span class="text-muted-foreground font-normal">{{ measured }}</span>
        </div>
      </div>

      <div class="ml-auto flex items-center gap-2 shrink-0" @click.stop>
        <!-- Where it can be seen. Only the published run has anywhere to point. -->
        <VisibleAt v-if="published && marketplaces?.length" :marketplaces="marketplaces" />
        <!-- What the run is, not what pressing it would do — and as plain a
             word as that: a chip here would compete with the one thing on this
             card that is meant to be pressed. -->
        <span class="text-xs" :class="published ? 'text-primary' : 'text-muted-foreground'">
          {{ published ? 'Public' : 'Private' }}
        </span>
      </div>
    </div>

    <div v-if="open" class="border-t border-border/60 p-3 sm:p-4 space-y-4">
      <CardFigures :card="card" />

      <CardCharts
        :answerable="card.answerable"
        :models="card.models"
        :skills="card.skills"
        :pressure="card.pressure"
        :stability="card.stability"
      />

      <!-- Everything that leaves this card, at its foot: what this page is
           for on the left, the way deeper into it on the right. -->
      <div class="flex items-center justify-between gap-2">
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
        <Button
          variant="outline"
          size="sm"
          class="h-7 px-2.5 text-xs ml-auto"
          @click="emit('more')"
        >
          More data
          <ChevronRight class="h-3.5 w-3.5 ml-1" />
        </Button>
      </div>
    </div>
  </section>
</template>
