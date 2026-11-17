<template>
  <Input
    :id="id"
    type="number"
    inputmode="decimal"
    :min="min"
    :max="max"
    :step="step"
    :model-value="Number.isFinite(modelValue) ? modelValue : ''"
    :class="widthClass"
    @update:model-value="update"
  />
</template>

<script setup lang="ts">
/** A number box that always hands back a number; an emptied box gives NaN. */
import { Input } from '@/components/ui/input'

withDefaults(
  defineProps<{
    modelValue: number
    id?: string
    min?: number
    max?: number
    step?: number
    widthClass?: string
  }>(),
  { id: undefined, min: undefined, max: undefined, step: 1, widthClass: 'w-30' },
)

const emit = defineEmits<{ 'update:modelValue': [number] }>()

function update(raw: string | number): void {
  const text = String(raw).trim()
  emit('update:modelValue', text === '' ? NaN : Number(text))
}
</script>
