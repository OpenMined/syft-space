<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[520px]">
      <DialogHeader>
        <DialogTitle class="heading-3">Choose data source</DialogTitle>
        <DialogDescription>
          Pick where this dataset's content comes from. Credentials are kept in the browser until
          you create the dataset.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 mt-4">
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
                <span class="mr-2">{{ presentation(source.name).icon }}</span>
                {{ presentation(source.name).label }}
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
            </Label>
            <Input
              :id="`cred-${field.name}`"
              v-model="credentials[field.name]"
              :type="field.type"
              :placeholder="field.placeholder"
              class="w-full"
            />
          </div>
        </div>
      </div>

      <DialogFooter class="mt-8">
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
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetTypeInfoResponse } from '@/api/types'

interface FieldCopy {
  label?: string
  placeholder?: string
}

interface SourceCopy {
  label: string
  icon: string
  description?: string
  fields?: Record<string, FieldCopy>
}

// Presentation layer: all user-facing copy lives here, keyed by source type.
// The backend schema supplies structure (which fields, required, type/format)
// and is the fallback for labels/description when an entry is missing here.
const PRESENTATION: Record<string, SourceCopy> = {
  local_file: {
    label: 'Local files',
    icon: '📁',
    description: 'Files and folders from this machine.',
  },
  wordpress: {
    label: 'WordPress',
    icon: '📰',
    description: 'Posts and pages from a self-hosted WordPress site.',
    fields: {
      siteUrl: { label: 'Site URL', placeholder: 'https://example.com' },
      username: { label: 'Username', placeholder: 'wp-admin user_login' },
      applicationPassword: {
        label: 'Application password',
        placeholder: 'Generate under Users → Profile → Application Passwords',
      },
    },
  },
}

const presentation = (name: string): SourceCopy => PRESENTATION[name] ?? { label: name, icon: '🗂️' }

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
  return presentation(type.name).description ?? type.description
})

const requiredFields = computed(() => {
  const type = selectedType.value
  const schema = type?.browse_schema
  if (!type || !schema?.properties) return []
  const fieldCopy = presentation(type.name).fields ?? {}
  return (schema.required ?? []).map((name) => {
    const prop = schema.properties?.[name]
    const copy = fieldCopy[name]
    return {
      name,
      label: copy?.label ?? prop?.title ?? name,
      placeholder: copy?.placeholder ?? '',
      type: prop?.format === 'password' ? 'password' : 'text',
    }
  })
})

const canContinue = computed(() => {
  if (!selectedType.value) return false
  return requiredFields.value.every((f) => (credentials.value[f.name] ?? '').trim() !== '')
})

const reset = () => {
  selectedSourceId.value = ''
  credentials.value = {}
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
})

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)
</script>
