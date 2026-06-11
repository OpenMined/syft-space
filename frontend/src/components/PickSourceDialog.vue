<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[520px]">
      <DialogHeader>
        <DialogTitle class="heading-3">Choose data source</DialogTitle>
        <DialogDescription>
          Pick where this dataset's content comes from. Credentials are kept in the
          browser until you create the dataset.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 mt-4">
        <div class="space-y-2">
          <Label for="source-type" class="text-sm font-medium">
            Source type <span class="text-red-500">*</span>
          </Label>
          <Select v-model="selectedSourceId">
            <SelectTrigger id="source-type" class="w-full">
              <SelectValue placeholder="Select a source type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="source in SOURCE_TYPES" :key="source.id" :value="source.id">
                <span class="mr-2">{{ source.icon }}</span>
                {{ source.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-if="selectedSource" class="text-xs text-muted-foreground">
            {{ selectedSource.description }}
          </p>
        </div>

        <div v-if="selectedSource && selectedSource.credentialFields.length > 0" class="space-y-4">
          <div
            v-for="field in selectedSource.credentialFields"
            :key="field.name"
            class="space-y-2"
          >
            <Label :for="`cred-${field.name}`" class="text-sm font-medium">
              {{ field.label }}
              <span v-if="field.required" class="text-red-500">*</span>
            </Label>
            <Input
              :id="`cred-${field.name}`"
              v-model="credentials[field.name]"
              :type="field.type === 'password' ? 'password' : 'text'"
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
import { ref, computed, watch } from 'vue'
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

interface CredentialField {
  name: string
  label: string
  type: 'text' | 'password' | 'url'
  placeholder: string
  required: boolean
}

interface SourceType {
  id: string
  label: string
  description: string
  icon: string
  credentialFields: CredentialField[]
}

const SOURCE_TYPES: SourceType[] = [
  {
    id: 'local_file',
    label: 'Local files',
    description: 'Files and folders from this machine.',
    icon: '📁',
    credentialFields: [],
  },
  {
    id: 'wordpress',
    label: 'WordPress',
    description: 'Posts and pages from a self-hosted WordPress site via the REST API.',
    icon: '📰',
    credentialFields: [
      {
        name: 'siteUrl',
        label: 'Site URL',
        type: 'url',
        placeholder: 'https://example.com',
        required: true,
      },
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        placeholder: 'wp-admin user_login',
        required: true,
      },
      {
        name: 'applicationPassword',
        label: 'Application password',
        type: 'password',
        placeholder: 'Generate in Users → Profile → Application Passwords',
        required: true,
      },
    ],
  },
]

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

const selectedSourceId = ref<string>('')
const credentials = ref<Record<string, string>>({})

const selectedSource = computed(() =>
  SOURCE_TYPES.find((s) => s.id === selectedSourceId.value) ?? null,
)

const canContinue = computed(() => {
  if (!selectedSource.value) return false
  return selectedSource.value.credentialFields
    .filter((f) => f.required)
    .every((f) => (credentials.value[f.name] ?? '').trim() !== '')
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
  if (!selectedSource.value || !canContinue.value) return
  const trimmed: Record<string, string> = {}
  for (const field of selectedSource.value.credentialFields) {
    trimmed[field.name] = (credentials.value[field.name] ?? '').trim()
  }
  emit('continue', { sourceType: selectedSource.value.id, credentials: trimmed })
  reset()
  isOpen.value = false
}

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)
</script>
