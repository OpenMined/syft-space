<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[520px] max-h-[85vh] flex flex-col">
      <DialogHeader>
        <DialogTitle class="heading-3">Choose data source</DialogTitle>
        <DialogDescription>
          Pick where this dataset's content comes from. Credentials are kept in the browser until
          you create the dataset.
        </DialogDescription>
      </DialogHeader>

      <!-- Only the body scrolls, so a long field can never push Continue out
           of reach. Scrolling one axis clips the other, which would shear off
           an input's 3px focus ring — the padding gives the ring room and the
           matching negative margin keeps fields aligned with the header. -->
      <div class="space-y-6 mt-4 flex-1 overflow-y-auto min-h-0 -mx-1 px-1">
        <div class="space-y-2">
          <Label for="source-type" class="text-sm font-medium">
            Source type <span class="text-red-500">*</span>
          </Label>
          <Select v-model="selectedSourceId">
            <SelectTrigger id="source-type" class="w-full">
              <SelectValue
                :placeholder="loadError ? 'Failed to load sources' : 'Select a source type'"
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="source in browsableTypes" :key="source.name" :value="source.name">
                <span class="mr-2">{{ sourcePresentation(source.name).icon }}</span>
                {{ sourcePresentation(source.name).label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-if="loadError" class="text-xs text-destructive">{{ loadError }}</p>
          <p v-else-if="selectedType" class="text-xs text-muted-foreground">
            {{ selectedDescription }}
          </p>
        </div>

        <div v-if="requiredFields.length > 0" class="space-y-4">
          <div v-for="field in requiredFields" :key="field.name" class="space-y-2">
            <Label :for="`cred-${field.name}`" class="text-sm font-medium">
              {{ field.label }} <span class="text-red-500">*</span>
              <span
                v-if="field.isList && listCount(field.name) > 0"
                class="text-muted-foreground ml-1 font-normal"
              >
                ({{ listCount(field.name) }})
              </span>
            </Label>

            <ListRowsEditor
              v-if="field.isList"
              :model-value="listRows[field.name] ?? []"
              :label="field.label"
              :placeholder="field.placeholder"
              :separator="field.separator"
              @update:model-value="onRowsChange(field.name, $event)"
            />

            <Input
              v-else
              :id="`cred-${field.name}`"
              v-model="credentials[field.name]"
              :type="field.type"
              :placeholder="field.placeholder"
              class="w-full"
            />
          </div>
        </div>
      </div>

      <DialogFooter class="mt-6 flex-shrink-0">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button @click="handleContinue" :disabled="!canContinue">Continue</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { sourcePresentation } from '@/config/sources'
import ListRowsEditor from '@/components/ListRowsEditor.vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetTypeInfoResponse } from '@/api/types'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  continue: [payload: { sourceType: string; credentials: Record<string, string> }]
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const types = ref<DatasetTypeInfoResponse[]>([])
const loadError = ref<string | null>(null)
const selectedSourceId = ref<string>('')
const credentials = ref<Record<string, string>>({})

const loadTypes = async () => {
  try {
    loadError.value = null
    types.value = await datasetsApi.listTypes()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Failed to load source types'
  }
}

onMounted(loadTypes)

const browsableTypes = computed(() => types.value.filter((t) => t.browsable))

const selectedType = computed(
  () => browsableTypes.value.find((t) => t.name === selectedSourceId.value) ?? null,
)

const selectedDescription = computed(() => {
  const type = selectedType.value
  if (!type) return ''
  return sourcePresentation(type.name).description ?? type.description
})

const requiredFields = computed(() => {
  const type = selectedType.value
  const schema = type?.browse_schema
  if (!type || !schema?.properties) return []
  const fieldCopy = sourcePresentation(type.name).fields ?? {}
  return (schema.required ?? []).map((name) => {
    const prop = schema.properties?.[name]
    const copy = fieldCopy[name]
    return {
      name,
      label: copy?.label ?? prop?.title ?? name,
      placeholder: copy?.placeholder ?? '',
      type: prop?.format === 'password' ? 'password' : 'text',
      isList: Boolean(copy?.list),
      separator: copy?.list?.separator ?? ',',
    }
  })
})

// ── List fields ────────────────────────────────────────────────────────
// The backend takes one separated string per field, so the rows live here
// and are joined into `credentials` on every edit. Everything downstream —
// validation, canContinue, the emitted payload — still sees a plain string.

const listRows = ref<Record<string, string[]>>({})

const onRowsChange = (name: string, rows: string[]) => {
  listRows.value[name] = rows
  const field = requiredFields.value.find((f) => f.name === name)
  const seen = new Set<string>()
  const kept: string[] = []
  for (const row of rows) {
    const trimmed = row.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    kept.push(trimmed)
  }
  credentials.value[name] = kept.join(field?.separator ?? ',')
}

/** How many rows will actually be stored — blanks and duplicates excluded. */
const listCount = (name: string) => {
  const field = requiredFields.value.find((f) => f.name === name)
  const value = credentials.value[name] ?? ''
  return value === '' ? 0 : value.split(field?.separator ?? ',').length
}

const canContinue = computed(() => {
  if (!selectedType.value) return false
  return requiredFields.value.every((f) => (credentials.value[f.name] ?? '').trim() !== '')
})

const reset = () => {
  selectedSourceId.value = ''
  credentials.value = {}
  listRows.value = {}
}

const handleCancel = () => {
  reset()
  isOpen.value = false
}

const handleContinue = () => {
  if (!selectedType.value || !canContinue.value) return
  const trimmed: Record<string, string> = {}
  for (const field of requiredFields.value) {
    trimmed[field.name] = (credentials.value[field.name] ?? '').trim()
  }
  emit('continue', { sourceType: selectedType.value.name, credentials: trimmed })
  reset()
  isOpen.value = false
}

// Clear any entered credentials when switching source type.
watch(selectedSourceId, () => {
  credentials.value = {}
  listRows.value = {}
})

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)
</script>
