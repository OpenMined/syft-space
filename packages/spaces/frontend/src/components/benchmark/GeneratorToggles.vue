<script setup lang="ts">
/**
 * Which generators run, one row each — instead of typing their names into a
 * text box. Checked means enabled; the underlying setting is the list of
 * generators switched off, so this inverts on the way in and out.
 */
import { computed } from 'vue'
import { Checkbox } from '@/components/ui/checkbox'
import { generatorWords } from './labels'
import InfoTip from './InfoTip.vue'

const props = defineProps<{
  generators: string[]
  /** The `disabled_generators` value as it stands in the form right now. */
  modelValue: string[] | undefined
  /** What it falls back to when unset here — the connection's own layer. */
  inherited: string[] | undefined
}>()
const emit = defineEmits<{ 'update:modelValue': [string[] | undefined] }>()

const effectiveDisabled = computed(() => props.modelValue ?? props.inherited ?? [])

function enabled(key: string): boolean {
  return !effectiveDisabled.value.includes(key)
}

function toggle(key: string, on: boolean): void {
  const base = new Set(effectiveDisabled.value)
  if (on) {
    base.delete(key)
  } else {
    base.add(key)
  }
  // Order follows the generator list the benchmark gave, not click order.
  const next = props.generators.filter((g) => base.has(g))
  emit('update:modelValue', next.length ? next : undefined)
}
</script>

<template>
  <div class="grid sm:grid-cols-2 gap-x-4 gap-y-2">
    <label
      v-for="key in generators"
      :key="key"
      class="flex items-start gap-2 text-sm cursor-pointer"
    >
      <Checkbox
        :model-value="enabled(key)"
        class="mt-0.5"
        @update:model-value="(on) => toggle(key, on === true)"
      />
      <span class="flex items-center gap-1.5">
        {{ generatorWords(key).label }}
        <InfoTip v-if="generatorWords(key).help" :text="generatorWords(key).help!" />
      </span>
    </label>
  </div>
</template>
