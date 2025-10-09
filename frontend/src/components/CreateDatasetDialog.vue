<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[700px]">
      <DialogHeader>
        <DialogTitle>{{ isEditMode ? 'Edit Dataset' : 'Create Dataset' }}</DialogTitle>
      </DialogHeader>

      <!-- Step Indicator -->
      <div class="flex items-center justify-center py-4">
        <div class="flex items-center space-x-4">
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 0 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 0 ? 'text-gray-900' : 'text-gray-500'">
              Type Selection
            </span>
          </div>
          <div class="w-24 h-0.5 bg-gray-300">
            <div class="h-full bg-blue-500 transition-all" :style="{ width: currentStepIndex >= 1 ? '100%' : '0%' }"></div>
          </div>
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 1 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 1 ? 'text-gray-900' : 'text-gray-500'">
              Configuration
            </span>
          </div>
          <div class="w-24 h-0.5 bg-gray-300">
            <div class="h-full bg-blue-500 transition-all" :style="{ width: currentStepIndex >= 2 ? '100%' : '0%' }"></div>
          </div>
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 2 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 2 ? 'text-gray-900' : 'text-gray-500'">
              Done
            </span>
          </div>
        </div>
      </div>

      <Separator class="mb-6" />

      <div class="flex flex-col" style="height: 400px;">
        <!-- Type Selection Step -->
        <div v-if="currentStep === 'type-selection'" class="flex flex-col h-full">

          <!-- Search Input -->
          <div class="relative mb-4">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              v-model="searchQuery"
              placeholder="Search datasets..."
              class="pl-10 pr-4"
            />
          </div>

          <!-- Data Source Options Grid -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 overflow-y-auto flex-1 pr-2 pb-2">
            <div
              v-for="dataset in filteredDatasets"
              :key="dataset.id"
              @click="dataset.isCustom ? openCustomSDKDocs() : selectedDatasetType = dataset.id"
              :class="[
                'flex flex-col items-center justify-center p-6 rounded-lg border cursor-pointer transition-all group h-40',
                dataset.isCustom 
                  ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                  : (selectedDatasetType === dataset.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50')
              ]"
            >
              <div v-if="dataset.isCustom" class="transition-all duration-200 mb-2">
                <div class="p-2 bg-purple-100 rounded-md group-hover:hidden">
                  <Code class="h-6 w-6 text-purple-600" />
                </div>
                <div class="hidden group-hover:block p-2 bg-purple-100 rounded-md">
                  <ExternalLink class="h-6 w-6 text-purple-600" />
                </div>
              </div>
              <IntegrationIcon
                v-else
                :name="dataset.id"
                class="h-12 w-12 mb-3"
                :class="selectedDatasetType === dataset.id ? 'text-blue-600' : 'text-gray-600'"
              />
              <div v-if="dataset.isCustom" class="text-center transition-all duration-200 min-h-[1.25rem]">
                <span class="font-medium text-purple-800 group-hover:hidden">
                  {{ dataset.name }}
                </span>
                <span class="hidden group-hover:block font-medium text-purple-800">
                  View documentation
                </span>
              </div>
              <span v-else class="font-medium text-center" :class="selectedDatasetType === dataset.id ? 'text-blue-900' : 'text-gray-900'">
                {{ dataset.name }}
              </span>
              <div v-if="dataset.isCustom" class="text-center transition-all duration-200 min-h-[1rem]">
                <span class="text-xs text-purple-600 group-hover:hidden">Using SDK</span>
                <span class="hidden group-hover:block text-xs text-purple-600">Opens in a new tab</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Configuration Step -->
        <div v-if="currentStep === 'configuration'" class="space-y-3">
          <div>
            <h3 class="text-lg font-semibold">Configure {{ selectedDatasetName }}</h3>
            <p class="text-sm text-muted-foreground">
              Set up your {{ selectedDatasetName }} dataset settings
            </p>
          </div>
          <div class="min-h-[200px] flex items-center justify-center border-2 border-dashed rounded-lg">
            <p class="text-muted-foreground">Configuration form for {{ selectedDatasetName }}</p>
          </div>
        </div>

        <!-- Done Step -->
        <div v-if="currentStep === 'done'" class="space-y-4">
          <div class="text-center py-8">
            <div class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <Check class="h-8 w-8 text-green-600" />
            </div>
            <h3 class="text-xl font-semibold mb-2">Dataset {{ isEditMode ? 'Updated' : 'Created' }} Successfully!</h3>
            <p class="text-gray-600">
              Your {{ selectedDatasetName }} dataset has been {{ isEditMode ? 'updated' : 'created' }} and is ready to use.
            </p>
          </div>
        </div>
      </div>

      <Separator class="mt-4 mb-4" />

      <DialogFooter>
        <!-- Type Selection Step Buttons -->
        <div v-if="currentStep === 'type-selection'" class="flex justify-between w-full">
          <Button variant="ghost" @click="handleCancel">
            Cancel
          </Button>
          <Button @click="goToNextStep" :disabled="!selectedDatasetType">
            Next
          </Button>
        </div>

        <!-- Configuration Step Buttons -->
        <div v-if="currentStep === 'configuration'" class="flex justify-between w-full">
          <Button variant="ghost" @click="goToPreviousStep">
            Previous
          </Button>
          <Button @click="handleCreate">
            {{ isEditMode ? 'Update' : 'Create' }}
          </Button>
        </div>

        <!-- Done Step Buttons -->
        <div v-if="currentStep === 'done'" class="flex justify-end w-full">
          <Button @click="handleClose">
            Close
          </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

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
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Search, ChevronRight, Check, Code, ExternalLink, X } from 'lucide-vue-next'
import IntegrationIcon from '@/components/IntegrationIcons.vue'

type Step = 'type-selection' | 'configuration' | 'done'

interface DataSource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
}

const props = defineProps<{
  open: boolean
  dataset?: DataSource | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'dataset-created': []
  'dataset-updated': []
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const currentStep = ref<Step>('type-selection')
const searchQuery = ref('')
const selectedDatasetType = ref<string | null>(null)

const isEditMode = computed(() => !!props.dataset)

const datasetOptions = [
  { id: 'filesystem', name: 'File System', type: 'Data' },
  { id: 'weaviate', name: 'Weaviate', type: 'Data' },
  { id: 'qdrant', name: 'Qdrant', type: 'Data' },
  { id: 'chroma', name: 'Chroma', type: 'Data' },
  { id: 'custom', name: 'Custom', type: 'Data', isCustom: true },
]

const currentStepIndex = computed(() => {
  const steps: Step[] = ['type-selection', 'configuration', 'done']
  return steps.indexOf(currentStep.value)
})

const filteredDatasets = computed(() => {
  if (!searchQuery.value) return datasetOptions
  return datasetOptions.filter(dataset => 
    dataset.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const selectedDatasetName = computed(() => {
  const dataset = datasetOptions.find(d => d.id === selectedDatasetType.value)
  return dataset?.name || 'Dataset'
})

const goToNextStep = () => {
  if (currentStep.value === 'type-selection') {
    currentStep.value = 'configuration'
  } else if (currentStep.value === 'configuration') {
    currentStep.value = 'done'
  }
}

const goToPreviousStep = () => {
  if (currentStep.value === 'configuration') {
    currentStep.value = 'type-selection'
  }
}

const handleCancel = () => {
  resetDialog()
  isOpen.value = false
}

const handleCreate = () => {
  goToNextStep()
  if (isEditMode.value) {
    emit('dataset-updated')
  } else {
    emit('dataset-created')
  }
}

const handleClose = () => {
  resetDialog()
  isOpen.value = false
}

const resetDialog = () => {
  currentStep.value = 'type-selection'
  selectedDatasetType.value = null
  searchQuery.value = ''
}

// Open custom SDK documentation
const openCustomSDKDocs = () => {
  window.open('https://docs.openmined.org/custom-data-sources', '_blank')
}

// Watch for dataset prop changes to populate form in edit mode
watch(() => props.dataset, (newDataset) => {
  if (newDataset && props.open) {
    selectedDatasetType.value = newDataset.type
    currentStep.value = 'configuration'
  }
}, { immediate: true })

// Watch for dialog open state to reset or populate form
watch(() => props.open, (isOpen) => {
  if (isOpen && props.dataset) {
    // Editing mode - populate form
    selectedDatasetType.value = props.dataset.type
    currentStep.value = 'configuration'
  } else if (isOpen && !props.dataset) {
    // Creation mode - reset form
    resetDialog()
  }
})
</script>