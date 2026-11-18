<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-4">
      <p class="text-xs text-muted-foreground">
        Which fields a caller may filter queries on. With every field ticked, fields declared later
        count too.
      </p>
      <div class="flex items-center gap-2 shrink-0">
        <Label for="filters-allowed" class="text-xs font-normal">Allow filtering</Label>
        <Switch id="filters-allowed" :model-value="!disabled" @update:model-value="setAllowed" />
      </div>
    </div>

    <TooltipProvider>
      <div
        :class="['rounded-md border border-input divide-y divide-border', disabled && 'opacity-50']"
      >
        <div
          v-for="row in rows"
          :key="row.name"
          class="flex items-center gap-3 px-3 py-2"
          :data-field="row.name"
        >
          <Checkbox
            :id="`filter-${row.name}`"
            :model-value="row.checked"
            :disabled="disabled || row.spec === null"
            @update:model-value="setChecked(row.name, $event === true)"
          />
          <Label
            :for="`filter-${row.name}`"
            :class="[
              'font-mono font-normal flex-1 min-w-0 truncate',
              row.spec === null && 'line-through text-muted-foreground',
            ]"
          >
            {{ row.name }}
          </Label>
          <Tooltip v-if="row.spec">
            <TooltipTrigger as-child>
              <Badge variant="secondary" class="font-normal cursor-default">
                {{ row.spec.type }}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>Operators: {{ row.spec.ops.join(', ') }}</p>
            </TooltipContent>
          </Tooltip>
          <span v-else class="text-xs text-muted-foreground">no longer declared</span>
        </div>
      </div>
    </TooltipProvider>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { FilterSchema } from '@/api/types'
import { allowlistFor, filterRows, filteringDisabled, type Allowlist } from '@/lib/filterableFields'

const props = defineProps<{
  schema: FilterSchema
  modelValue: Allowlist
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Allowlist]
}>()

const disabled = computed(() => filteringDisabled(props.modelValue))
const rows = computed(() => filterRows(props.schema, props.modelValue))

// Turning filtering back on restores every field rather than the list from
// before: the owner sees all ticked and unticks from there.
const setAllowed = (allowed: boolean) => emit('update:modelValue', allowed ? null : [])

const setChecked = (name: string, checked: boolean) => {
  const ticked = rows.value.filter((r) => r.spec !== null && r.checked).map((r) => r.name)
  const next = checked ? [...ticked, name] : ticked.filter((n) => n !== name)
  emit('update:modelValue', allowlistFor(props.schema, next))
}
</script>
