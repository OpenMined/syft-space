<template>
  <div class="space-y-2">
    <div
      v-for="(entry, index) in modelValue"
      :key="index"
      class="grid grid-cols-[1fr_1.4fr_auto] items-center gap-2"
    >
      <Input
        :model-value="entry.key"
        :placeholder="`${capitalized} name`"
        :disabled="entry.stored"
        class="font-mono text-sm"
        @update:model-value="updateEntry(index, { key: String($event) })"
      />
      <div class="flex items-center gap-2 min-w-0">
        <template v-if="entry.stored && entry.value === null">
          <span class="text-xs text-muted-foreground flex items-center gap-1 flex-1">
            <Lock class="h-3 w-3" /> Configured
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="h-7 text-xs"
            @click="updateEntry(index, { value: '' })"
          >
            Replace
          </Button>
        </template>
        <Input
          v-else
          :model-value="entry.value ?? ''"
          type="password"
          autocomplete="new-password"
          :placeholder="entry.stored ? 'New value' : 'Value'"
          class="text-sm"
          @update:model-value="updateEntry(index, { value: String($event) })"
        />
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
        :aria-label="`Remove ${entry.key || entryLabel}`"
        @click="removeEntry(index)"
      >
        <X class="h-3.5 w-3.5" />
      </Button>
    </div>
    <Button type="button" variant="outline" size="sm" class="h-7 text-xs" @click="addEntry">
      <Plus class="h-3 w-3 mr-1" /> Add {{ entryLabel }}
    </Button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Lock, Plus, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { SecretMapEntry } from '@/lib/datasetConfig'

// Edits a map whose stored values the client never sees. A stored entry
// shows as "Configured" until Replace reveals an input; a removed entry
// is simply absent from what the parent sends.
const props = withDefaults(
  defineProps<{
    modelValue: SecretMapEntry[]
    // What one entry is called, e.g. "header".
    entryLabel?: string
  }>(),
  { entryLabel: 'entry' },
)

const capitalized = computed(
  () => props.entryLabel.charAt(0).toUpperCase() + props.entryLabel.slice(1),
)

const emit = defineEmits<{
  'update:modelValue': [entries: SecretMapEntry[]]
}>()

const updateEntry = (index: number, change: Partial<SecretMapEntry>) => {
  const next = props.modelValue.map((entry, i) => (i === index ? { ...entry, ...change } : entry))
  emit('update:modelValue', next)
}

const removeEntry = (index: number) => {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index),
  )
}

const addEntry = () => {
  emit('update:modelValue', [...props.modelValue, { key: '', value: '', stored: false }])
}
</script>
