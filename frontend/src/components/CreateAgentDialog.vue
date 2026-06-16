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
import { Plus, X, Search, ArrowLeft, Sparkles, Server, Folder } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import {
  mockAgents,
  ORCHESTRATORS,
  AVAILABLE_SKILLS,
  AVAILABLE_MCPS,
  AVAILABLE_FOLDERS,
  getOrchestratorLabel,
  type Orchestrator,
} from '@/stores/mockAgents'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean]; 'agent-created': [] }>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

type AccessKey = 'skills' | 'mcps' | 'folders'

const step = ref<1 | 2>(1)
const accessSearch = ref('')

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

const accessGroups = [
  { key: 'skills' as const, label: 'Skills', pool: AVAILABLE_SKILLS, icon: Sparkles, mono: false },
  { key: 'mcps' as const, label: 'MCPs', pool: AVAILABLE_MCPS, icon: Server, mono: false },
  { key: 'folders' as const, label: 'Folders', pool: AVAILABLE_FOLDERS, icon: Folder, mono: true },
]

const isFormValid = computed(() => formData.value.name.trim() !== '')

const selectedTotal = computed(
  () =>
    formData.value.skills.length + formData.value.mcps.length + formData.value.folders.length,
)

const toggle = (list: string[], value: boolean, item: string) => {
  if (value) {
    if (!list.includes(item)) list.push(item)
  } else {
    const idx = list.indexOf(item)
    if (idx !== -1) list.splice(idx, 1)
  }
}

const filterPool = (pool: string[]) =>
  pool.filter((item) => item.toLowerCase().includes(accessSearch.value.trim().toLowerCase()))

const isAllSelected = (key: AccessKey, pool: string[]) =>
  pool.every((item) => formData.value[key].includes(item))

const toggleAll = (key: AccessKey, pool: string[]) => {
  formData.value[key] = isAllSelected(key, pool) ? [] : [...pool]
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
  step.value = 1
  accessSearch.value = ''
  formData.value = {
    name: '',
    description: '',
    orchestrator: 'claude',
    // Everything Claude reports access to is selected by default.
    skills: [...AVAILABLE_SKILLS],
    mcps: [...AVAILABLE_MCPS],
    folders: [...AVAILABLE_FOLDERS],
    tags: [],
  }
  tagInput.value = ''
}

const goToAccess = () => {
  if (!isFormValid.value) return
  accessSearch.value = ''
  step.value = 2
}

const goBack = () => {
  step.value = 1
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
        <div class="flex items-center gap-3">
          <DialogTitle class="heading-3">
            {{ step === 1 ? 'Add Agent' : `Connect ${getOrchestratorLabel(formData.orchestrator)}` }}
          </DialogTitle>
          <span class="text-xs text-muted-foreground">Step {{ step }} of 2</span>
        </div>
      </DialogHeader>

      <!-- Step 1: basics -->
      <div v-if="step === 1" class="space-y-6 mt-6">
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
            The session engine that drives this agent. We'll scan its skills, MCPs and folders
            next.
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
              <button
                class="ml-2 hover:text-destructive transition-colors"
                @click="removeTag(index)"
              >
                <X class="h-3 w-3" />
              </button>
            </Badge>
          </div>
        </div>
      </div>

      <!-- Step 2: discovered access browser -->
      <div v-else class="space-y-4 mt-6">
        <p class="text-sm text-muted-foreground">
          We found the following in your local
          <span class="font-medium text-foreground">{{
            getOrchestratorLabel(formData.orchestrator)
          }}</span>
          — <span class="font-medium text-foreground">{{ selectedTotal }}</span> selected. Untick
          anything you don't want this agent to expose.
        </p>

        <div class="relative">
          <Search
            class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none"
          />
          <Input
            v-model="accessSearch"
            placeholder="Search skills, MCPs, folders..."
            class="pl-9"
          />
        </div>

        <div class="space-y-4">
          <div
            v-for="group in accessGroups"
            :key="group.key"
            class="rounded-lg border border-border/60"
          >
            <div class="flex items-center justify-between px-3 py-2 border-b border-border/60">
              <div class="flex items-center gap-2">
                <component :is="group.icon" class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-medium text-foreground">{{ group.label }}</span>
                <Badge variant="secondary" class="text-[11px]">
                  {{ formData[group.key].length }}/{{ group.pool.length }}
                </Badge>
              </div>
              <button
                class="text-xs text-muted-foreground hover:text-foreground transition-colors"
                @click="toggleAll(group.key, group.pool)"
              >
                {{ isAllSelected(group.key, group.pool) ? 'Deselect all' : 'Select all' }}
              </button>
            </div>
            <div class="p-3 space-y-2">
              <label
                v-for="item in filterPool(group.pool)"
                :key="item"
                class="flex items-center gap-2.5 text-sm cursor-pointer"
                :class="group.mono ? 'font-mono text-xs' : ''"
              >
                <Checkbox
                  :model-value="formData[group.key].includes(item)"
                  @update:model-value="toggle(formData[group.key], $event as boolean, item)"
                />
                {{ item }}
              </label>
              <p
                v-if="filterPool(group.pool).length === 0"
                class="text-xs text-muted-foreground italic"
              >
                No matches
              </p>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-8">
        <template v-if="step === 1">
          <Button variant="outline" @click="handleCancel">Cancel</Button>
          <Button :disabled="!isFormValid" @click="goToAccess">Continue</Button>
        </template>
        <template v-else>
          <Button variant="outline" @click="goBack">
            <ArrowLeft class="h-4 w-4 mr-1" />
            Back
          </Button>
          <Button :disabled="!isFormValid" @click="handleCreate">Add Agent</Button>
        </template>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
