<template>
  <Dialog v-model:open="open">
    <DialogContent class="sm:max-w-[560px]" data-testid="combine-dialog">
      <template v-if="differences.length">
        <DialogHeader>
          <DialogTitle>Runs differ</DialogTitle>
          <DialogDescription>{{ tooFew ? TOO_FEW : DIFFER }}</DialogDescription>
        </DialogHeader>
        <div
          v-if="!tooFew"
          class="max-h-[50vh] space-y-3 overflow-y-auto text-sm"
          data-testid="combine-differences"
        >
          <div
            v-for="d in shownDifferences"
            :key="d.field"
            class="space-y-1"
            data-testid="combine-difference"
          >
            <span class="text-xs font-semibold">{{ settingLabel(d.field) }}</span>
            <div
              v-for="v in d.values"
              :key="v.job_id"
              class="flex gap-3 text-xs text-muted-foreground"
            >
              <span class="w-36 shrink-0 tabular-nums">{{ runNameById(v.job_id, runs) }}</span>
              <span class="min-w-0 break-all text-foreground">{{ settingValue(v.value) }}</span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="open = false">Close</Button>
        </DialogFooter>
      </template>

      <template v-else>
        <DialogHeader>
          <DialogTitle>Combine runs</DialogTitle>
          <DialogDescription data-testid="combine-count">{{ countText }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-1.5">
          <Label for="combine-title" class="text-xs text-muted-foreground">Title</Label>
          <Input
            id="combine-title"
            v-model="title"
            placeholder="Optional"
            data-testid="combine-title"
            @keydown.enter="submit"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="creating" @click="open = false">Cancel</Button>
          <Button :disabled="creating" data-testid="combine-confirm" @click="submit">
            Combine
          </Button>
        </DialogFooter>
      </template>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
/** Combining checked runs: what differs when they cannot be combined, else an optional title. */
import { computed, ref, watch } from 'vue'
import type { BenchmarkCombineDifference, BenchmarkRunSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { plural, settingLabel } from '../labels'
import { runNameById, settingValue } from './combined'

const TOO_FEW = 'Pick at least two different runs.'
const DIFFER = 'These runs were not measured the same way.'

const props = defineProps<{
  /** Runs to be combined, combined runs flattened. */
  members: number
  repeated: number
  differences: BenchmarkCombineDifference[]
  /** The listed runs, to name runs by. */
  runs: BenchmarkRunSummary[]
  creating: boolean
}>()

const emit = defineEmits<{ confirm: [title: string] }>()

const open = defineModel<boolean>('open', { required: true })

const title = ref('')
watch(open, (shown) => {
  if (shown) title.value = ''
})

const tooFew = computed(() => props.differences.some((d) => d.field === 'members'))
const shownDifferences = computed(() => props.differences.filter((d) => d.values.length))

const countText = computed(() => {
  const runs = plural(props.members, 'run', 'runs')
  return props.repeated > 0
    ? `${runs} · ${plural(props.repeated, 'repeated question', 'repeated questions')}`
    : runs
})

function submit(): void {
  if (!props.creating) emit('confirm', title.value.trim())
}
</script>
