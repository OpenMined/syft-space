<template>
  <Select :model-value="toItem(modelValue)" @update:model-value="pick">
    <SelectTrigger :id="id" :class="widthClass">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem v-for="choice in choices" :key="choice.value" :value="toItem(choice.value)">
        {{ choice.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>

<script setup lang="ts">
/** A dropdown of fixed choices; an empty value is allowed as one of them. */
import type { AcceptableValue } from 'reka-ui'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Choice } from './setupForm'

withDefaults(
  defineProps<{ modelValue: string; choices: Choice[]; id?: string; widthClass?: string }>(),
  { id: undefined, widthClass: 'w-70' },
)

const emit = defineEmits<{ 'update:modelValue': [string] }>()

// The select reserves '' for "nothing chosen".
const EMPTY = '__empty__'

function toItem(value: string): string {
  return value === '' ? EMPTY : value
}

function pick(value: AcceptableValue): void {
  const text = String(value ?? '')
  emit('update:modelValue', text === EMPTY ? '' : text)
}
</script>
