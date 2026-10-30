<script setup lang="ts">
/** One provider role: what it sends and where, its address, and its key (saved on its own). */
import { computed, ref } from 'vue'
import Hint from '@/components/benchmark/Hint.vue'
import InfoTip from '@/components/benchmark/InfoTip.vue'
import LocalityChip from '@/components/benchmark/LocalityChip.vue'
import { TONE } from '@/components/benchmark/labels'
import { localityTip, type KeySource } from '@/components/benchmark/modelAccess'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const props = defineProps<{
  label: string
  tip: string
  /** What the role sends; empty for a role that sends nothing itself. */
  sends: string
  url: string
  /** Shown in an empty address box: what a blank address resolves to. */
  placeholder: string
  /** The address the role actually calls. */
  target: string
  /** Whether `target` stays inside the perimeter, as the benchmark judged it; null when unknown. */
  local: boolean | null
  /** Whether a key is stored for the role; null when the benchmark's keys could not be read. */
  keySet: boolean | null
  keySource: KeySource
  busy: boolean
  /** Stores a key; resolves true once stored. */
  saveKey: (value: string) => Promise<boolean>
}>()

const KEY_LABELS: Record<KeySource, string> = {
  own: 'Key set',
  inherited: 'Inherited key',
  none: 'No key',
  unknown: 'Key unknown',
}

const KEY_HINTS: Partial<Record<KeySource, string>> = {
  inherited: 'Uses the key of the role it follows.',
  unknown: 'The benchmark did not list its keys.',
}

const emit = defineEmits<{
  'update:url': [string]
  clearKey: []
}>()

const keyInput = ref('')

const whereTip = computed(() => localityTip(props.target, !!props.local, 'Sent to'))

/** The typed key stays in the box until the save succeeds, so a refusal does not lose it. */
async function submitKey() {
  const value = keyInput.value
  if (!value) return
  if (await props.saveKey(value)) keyInput.value = ''
}
</script>

<template>
  <div class="border border-border/50 rounded-md p-3 space-y-2">
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-0.5">
        <p class="flex items-center gap-1.5 text-sm font-medium text-foreground">
          {{ label }}
          <InfoTip :text="tip" />
        </p>
        <p v-if="sends" class="text-xs text-muted-foreground">
          Sends: <span class="text-foreground">{{ sends }}</span>
        </p>
      </div>
      <div class="flex items-center gap-1.5 shrink-0">
        <LocalityChip v-if="sends && local !== null" :local="local" :tip="whereTip" />
        <Hint :text="KEY_HINTS[keySource] ?? null">
          <span
            class="text-xs px-2 py-1 rounded-md"
            :class="keySource === 'own' ? TONE.good : TONE.muted"
          >
            {{ KEY_LABELS[keySource] }}
          </span>
        </Hint>
      </div>
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <div class="space-y-1">
        <Label class="text-xs">Address</Label>
        <Input
          :model-value="url"
          :placeholder="placeholder || 'default'"
          class="h-8 text-xs"
          @update:model-value="(v) => emit('update:url', String(v))"
        />
      </div>
      <div class="space-y-1">
        <Label class="text-xs">Key</Label>
        <div class="flex gap-1.5">
          <Input
            v-model="keyInput"
            type="password"
            :placeholder="keySet ? 'Stored — leave blank to keep it' : ''"
            class="h-8 text-xs"
            :disabled="props.busy"
          />
          <Button
            v-if="keyInput"
            size="sm"
            variant="outline"
            class="h-8 px-2 text-xs"
            :disabled="props.busy"
            @click="submitKey"
          >
            Save
          </Button>
          <Button
            v-else-if="keySet === true"
            size="sm"
            variant="ghost"
            class="h-8 px-2 text-xs text-destructive hover:text-destructive"
            :disabled="props.busy"
            @click="emit('clearKey')"
          >
            Clear
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
