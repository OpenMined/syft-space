<template>
  <div class="space-y-6">
    <div v-for="group in groups" :key="group.axis" class="space-y-4">
      <h4
        v-if="groups.length > 1"
        class="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {{ group.label }}
      </h4>

      <div v-for="field in group.fields" :key="field.name" class="space-y-2">
        <Label :for="`cfg-${field.name}`" class="text-sm font-medium">
          {{ field.label }} <span v-if="field.required" class="text-red-500">*</span>
        </Label>

        <!-- Secret scalar: the stored value is never shown. -->
        <template v-if="field.kind === 'secret'">
          <div
            v-if="!revealed[field.name]"
            class="flex items-center justify-between rounded-md border border-input px-3 py-2"
          >
            <span class="text-sm text-muted-foreground flex items-center gap-1.5">
              <Lock class="h-3.5 w-3.5" /> Configured
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              class="h-7 text-xs"
              @click="reveal(field.name)"
            >
              Replace
            </Button>
          </div>
          <div v-else class="flex items-center gap-2">
            <Input
              :id="`cfg-${field.name}`"
              :model-value="secretValue(field)"
              type="password"
              autocomplete="new-password"
              placeholder="New value"
              class="flex-1"
              @update:model-value="setSecret(field, String($event))"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              class="h-8 text-xs"
              @click="keepSecret(field)"
            >
              Keep current
            </Button>
          </div>
        </template>

        <SecretMapEditor
          v-else-if="field.kind === 'secretMap'"
          :model-value="mapEntries(field)"
          :entry-label="field.entryLabel"
          @update:model-value="emit('update', field.name, { kind: 'secretMap', entries: $event })"
        />

        <ListRowsEditor
          v-else-if="field.kind === 'list'"
          :model-value="rows(field)"
          :label="field.label"
          :placeholder="field.placeholder"
          :separator="field.separator ?? ','"
          @update:model-value="emit('update', field.name, { kind: 'rows', rows: $event })"
        />

        <Select
          v-else-if="field.kind === 'select'"
          :model-value="value(field)"
          @update:model-value="emit('update', field.name, { kind: 'value', value: String($event) })"
        >
          <SelectTrigger :id="`cfg-${field.name}`" class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="option in field.options" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Input
          v-else
          :id="`cfg-${field.name}`"
          :model-value="value(field)"
          :type="field.kind === 'number' ? 'number' : 'text'"
          :min="field.min"
          :max="field.max"
          :step="field.kind === 'number' ? 'any' : undefined"
          :placeholder="field.placeholder"
          class="w-full"
          @update:model-value="emit('update', field.name, { kind: 'value', value: String($event) })"
        />

        <p v-if="errors[field.name]" class="text-xs text-destructive">{{ errors[field.name] }}</p>
        <p v-else-if="field.description" class="text-xs text-muted-foreground">
          {{ field.description }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Lock } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import ListRowsEditor from '@/components/ListRowsEditor.vue'
import SecretMapEditor from '@/components/SecretMapEditor.vue'
import type { ConfigAxis, ConfigField, FieldDraft, SecretMapEntry } from '@/lib/datasetConfig'

// Renders editable configuration fields grouped by axis. Holds no state of
// its own beyond which secrets are being replaced; every edit is emitted as
// the field's new draft and the owner decides what it means.
const props = defineProps<{
  groups: Array<{ axis: ConfigAxis; label: string; fields: ConfigField[] }>
  drafts: Record<string, FieldDraft>
  errors: Record<string, string>
}>()

const emit = defineEmits<{
  update: [name: string, draft: FieldDraft]
}>()

const revealed = ref<Record<string, boolean>>({})

const draft = (field: ConfigField): FieldDraft | undefined => props.drafts[field.name]

const value = (field: ConfigField): string => {
  const d = draft(field)
  return d?.kind === 'value' ? d.value : ''
}

const rows = (field: ConfigField): string[] => {
  const d = draft(field)
  return d?.kind === 'rows' ? d.rows : []
}

const mapEntries = (field: ConfigField): SecretMapEntry[] => {
  const d = draft(field)
  return d?.kind === 'secretMap' ? d.entries : []
}

const secretValue = (field: ConfigField): string => {
  const d = draft(field)
  return d?.kind === 'secret' ? d.replacement : ''
}

const reveal = (name: string) => {
  revealed.value = { ...revealed.value, [name]: true }
}

const setSecret = (field: ConfigField, replacement: string) => {
  emit('update', field.name, { kind: 'secret', replacement })
}

const keepSecret = (field: ConfigField) => {
  revealed.value = { ...revealed.value, [field.name]: false }
  emit('update', field.name, { kind: 'secret', replacement: '' })
}
</script>
