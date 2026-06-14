<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import {
  mockAgents,
  ORCHESTRATORS,
  AVAILABLE_SKILLS,
  AVAILABLE_MCPS,
  AVAILABLE_FOLDERS,
  type Orchestrator,
} from '@/stores/mockAgents'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean]; 'agent-created': [] }>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const formData = ref({
  name: '',
  description: '',
  orchestrator: 'claude' as Orchestrator,
  skills: [] as string[],
  mcps: [] as string[],
  folders: [] as string[],
  tags: [] as string[],
})
const tagInput = ref('')

const isFormValid = computed(() => formData.value.name.trim() !== '')

const toggle = (list: string[], value: boolean, item: string) => {
  if (value) {
    if (!list.includes(item)) list.push(item)
  } else {
    const idx = list.indexOf(item)
    if (idx !== -1) list.splice(idx, 1)
  }
}

const addTag = () => {
  const tag = tagInput.value.trim().toLowerCase()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}
const removeTag = (index: number) => formData.value.tags.splice(index, 1)

const slugify = (name: string) =>
  name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')

const resetForm = () => {
  formData.value = {
    name: '',
    description: '',
    orchestrator: 'claude',
    skills: [],
    mcps: [],
    folders: [],
    tags: [],
  }
  tagInput.value = ''
}

const handleCancel = () => {
  resetForm()
  isOpen.value = false
}

const handleCreate = () => {
  if (!isFormValid.value) return
  const id = slugify(formData.value.name) || `agent-${Date.now()}`
  if (mockAgents.some((a) => a.id === id)) {
    toast.error('An agent with that name already exists')
    return
  }
  mockAgents.push({
    id,
    name: formData.value.name.trim(),
    description: formData.value.description.trim(),
    tags: [...formData.value.tags],
    orchestrator: formData.value.orchestrator,
    skills: [...formData.value.skills],
    mcps: [...formData.value.mcps],
    folders: [...formData.value.folders],
    status: 'active',
    sessions: 1,
    lastUpdated: new Date(),
    endpointCount: 0,
  })
  toast.success(`"${formData.value.name}" added`)
  emit('agent-created')
  resetForm()
  isOpen.value = false
}

watch(isOpen, (open) => {
  if (open) resetForm()
})
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">Add Agent</DialogTitle>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Name -->
        <div class="space-y-2">
          <Label for="agent-name" class="text-sm font-medium">
            Name <span class="text-red-500">*</span>
          </Label>
          <Input
            id="agent-name"
            v-model="formData.name"
            placeholder="e.g., Personal Assistant"
            class="w-full"
          />
        </div>

        <!-- Orchestrator -->
        <div class="space-y-2">
          <Label for="orchestrator" class="text-sm font-medium">
            Orchestrator <span class="text-red-500">*</span>
          </Label>
          <Select v-model="formData.orchestrator">
            <SelectTrigger id="orchestrator" class="w-full">
              <SelectValue placeholder="Select an orchestrator" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="o in ORCHESTRATORS" :key="o.id" :value="o.id">
                {{ o.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs text-muted-foreground">
            The session engine that drives this agent.
          </p>
        </div>

        <!-- Description -->
        <div class="space-y-2">
          <Label for="agent-description" class="text-sm font-medium">Description</Label>
          <Input
            id="agent-description"
            v-model="formData.description"
            placeholder="What is this agent for?"
            class="w-full"
          />
        </div>

        <!-- Imported access: Skills / MCPs / Folders -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="space-y-2">
            <Label class="text-sm font-medium">Skills</Label>
            <div class="space-y-2 rounded-lg border border-border/60 p-3">
              <label
                v-for="skill in AVAILABLE_SKILLS"
                :key="skill"
                class="flex items-center gap-2.5 text-sm cursor-pointer"
              >
                <Checkbox
                  :model-value="formData.skills.includes(skill)"
                  @update:model-value="toggle(formData.skills, $event as boolean, skill)"
                />
                {{ skill }}
              </label>
            </div>
          </div>

          <div class="space-y-2">
            <Label class="text-sm font-medium">MCPs</Label>
            <div class="space-y-2 rounded-lg border border-border/60 p-3">
              <label
                v-for="mcp in AVAILABLE_MCPS"
                :key="mcp"
                class="flex items-center gap-2.5 text-sm cursor-pointer"
              >
                <Checkbox
                  :model-value="formData.mcps.includes(mcp)"
                  @update:model-value="toggle(formData.mcps, $event as boolean, mcp)"
                />
                {{ mcp }}
              </label>
            </div>
          </div>

          <div class="space-y-2">
            <Label class="text-sm font-medium">Folders</Label>
            <div class="space-y-2 rounded-lg border border-border/60 p-3">
              <label
                v-for="folder in AVAILABLE_FOLDERS"
                :key="folder"
                class="flex items-center gap-2.5 text-sm cursor-pointer font-mono text-xs"
              >
                <Checkbox
                  :model-value="formData.folders.includes(folder)"
                  @update:model-value="toggle(formData.folders, $event as boolean, folder)"
                />
                {{ folder }}
              </label>
            </div>
          </div>
        </div>

        <!-- Tags -->
        <div class="space-y-2">
          <Label for="agent-tags" class="text-sm font-medium">Tags</Label>
          <div class="flex gap-2">
            <Input
              id="agent-tags"
              v-model="tagInput"
              placeholder="e.g., assistant, research"
              class="flex-1"
              @keydown.enter.prevent="addTag"
            />
            <Button variant="outline" :disabled="!tagInput.trim()" @click="addTag">
              <Plus class="h-4 w-4" />
            </Button>
          </div>
          <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-3">
            <Badge
              v-for="(tag, index) in formData.tags"
              :key="index"
              variant="secondary"
              class="px-3 py-1"
            >
              {{ tag }}
              <button class="ml-2 hover:text-destructive transition-colors" @click="removeTag(index)">
                <X class="h-3 w-3" />
              </button>
            </Badge>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button :disabled="!isFormValid" @click="handleCreate">Add Agent</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
